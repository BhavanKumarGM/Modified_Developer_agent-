"""
Central Orchestrator — routes tasks to agents, manages pipeline execution,
broadcasts events over WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Optional

from app.agents.base_agent import AgentContext
from app.agents.conversation_agent import ConversationAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.code_generation_agent import CodeGenerationAgent
from app.agents.editing_agent import EditingAgent
from app.agents.repository_agent import RepositoryAgent
from app.agents.search_agent import SearchAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.review_agent import ReviewAgent
from app.agents.debug_agent import DebugAgent
from app.agents.git_agent import GitAgent
from app.agents.preview_agent import PreviewAgent
from app.core.llm_service import llm_service
from app.core.config import settings
from app.core.logging_context import message_id_var
from app.services import file_service
from app.services.import_check import find_missing_local_imports

logger = logging.getLogger(__name__)


EventCallback = Callable[[str, dict], None]

# Agent names the PlannerAgent is allowed to put in plan["tasks"][i]["agent"].
# "refactoring" and "debug" both route through EditingAgent/DebugAgent via
# _handle_editing with the matching intent; "review"/"repository"/"search"
# are handled as standalone informational tasks.
KNOWN_TASK_AGENTS = {"codegen", "editing", "refactoring", "debug", "review", "repository", "search"}

_TASK_AGENT_TO_INTENT = {
    "codegen": "build",
    "editing": "edit",
    "refactoring": "refactor",
    "debug": "debug",
}

FORCE_APPLY_PHRASES = ("apply anyway", "force apply", "skip review", "override review")


class Orchestrator:
    def __init__(self) -> None:
        self.conversation = ConversationAgent(llm_service)
        self.planner = PlannerAgent(llm_service)
        self.codegen = CodeGenerationAgent(llm_service)
        self.editing = EditingAgent(llm_service)
        self.repository = RepositoryAgent(llm_service)
        self.search = SearchAgent(llm_service)
        self.memory = MemoryAgent(llm_service)
        self.review = ReviewAgent(llm_service)
        self.debug = DebugAgent(llm_service)
        self.git = GitAgent(llm_service)
        self.preview = PreviewAgent(llm_service)

        # Callbacks registered per project_id
        self._callbacks: dict[str, list[EventCallback]] = {}

        # The asyncio.Task currently running handle_message for a project,
        # so a WebSocket "stop" message has something to cancel. See
        # register_task/unregister_task/cancel_active_task and
        # routers/chat.py (which creates the task) and main.py's WS handler
        # (which cancels it).
        self._active_tasks: dict[str, asyncio.Task] = {}

        # One asyncio.Lock per project, held around every disk write for
        # that project (_write_files / _apply_edits) so two concurrent
        # edits to the same project can't interleave writes to the same
        # file. Not a distributed lock — this is a single-process tool.
        self._write_locks: dict[str, asyncio.Lock] = {}

    def _get_write_lock(self, project_id: str) -> asyncio.Lock:
        lock = self._write_locks.get(project_id)
        if lock is None:
            lock = asyncio.Lock()
            self._write_locks[project_id] = lock
        return lock

    def register_task(self, project_id: str, task: "asyncio.Task") -> None:
        self._active_tasks[project_id] = task

    def unregister_task(self, project_id: str, task: "asyncio.Task") -> None:
        if self._active_tasks.get(project_id) is task:
            del self._active_tasks[project_id]

    def cancel_active_task(self, project_id: str) -> bool:
        """Cancel the in-flight generation/edit for a project, if any.
        Returns True if a running task was found and cancelled."""
        task = self._active_tasks.get(project_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def register_callback(self, project_id: str, cb: EventCallback) -> None:
        self._callbacks.setdefault(project_id, []).append(cb)

    def unregister_callback(self, project_id: str, cb: EventCallback) -> None:
        cbs = self._callbacks.get(project_id, [])
        if cb in cbs:
            cbs.remove(cb)

    def _emit(self, project_id: str, event_type: str, payload: dict) -> None:
        for cb in self._callbacks.get(project_id, []):
            try:
                cb(event_type, payload)
            except Exception:
                pass

    async def handle_message(
        self,
        project_id: str,
        project_name: str,
        framework: str,
        root_path: Optional[str],
        metadata: dict,
        conversation_history: list[dict],
        user_message: str,
        message_id: str,
    ) -> AsyncIterator[str]:
        """
        Main entry point. Streams tokens back while running agent pipeline.
        """
        # Every log line emitted anywhere during this turn — planner, every
        # agent, git, file writes — carries this id, so one turn can be
        # traced end-to-end regardless of which module logged the line.
        cid_token = message_id_var.set(message_id)
        try:
            async for token in self._handle_message_impl(
                project_id, project_name, framework, root_path, metadata,
                conversation_history, user_message, message_id,
            ):
                yield token
        finally:
            message_id_var.reset(cid_token)

    async def _handle_message_impl(
        self,
        project_id: str,
        project_name: str,
        framework: str,
        root_path: Optional[str],
        metadata: dict,
        conversation_history: list[dict],
        user_message: str,
        message_id: str,
    ) -> AsyncIterator[str]:
        context = AgentContext(
            project_id=project_id,
            project_name=project_name,
            framework=framework,
            root_path=root_path,
            metadata=metadata,
            conversation_history=conversation_history,
        )
        force_apply = any(p in user_message.lower() for p in FORCE_APPLY_PHRASES)

        logger.info(f"Turn start: project={project_id} message='{user_message[:80]}'")
        self._emit(project_id, "agent_status", {"agent": "planner", "status": "thinking", "task": "Analyzing request"})

        # 1. Plan
        plan_result = await self.planner.run(user_message, context)
        plan = plan_result.data
        intent = plan.get("intent", "build")

        self._emit(project_id, "agent_status", {"agent": "planner", "status": "done", "task": None})

        # 2. Dispatch: prefer the planner's ordered task list when it gave us
        # one, falling back to the single intent branch below when it's
        # empty/malformed (e.g. the planner's JSON parse failed upstream).
        tasks = self._validate_tasks(plan.get("tasks"))

        if tasks:
            async for token in self._execute_tasks(context, user_message, plan, tasks, message_id, force_apply):
                yield token
        elif intent in ("build",) and plan.get("requires_full_generation"):
            async for token in self._handle_generation(context, user_message, plan, message_id, force_apply=force_apply):
                yield token
        elif intent in ("edit", "refactor", "debug"):
            async for token in self._handle_editing(context, user_message, plan, intent, message_id, force_apply=force_apply):
                yield token
        else:
            # Conversation / explain / analyze
            async for token in self._handle_conversation(context, user_message, message_id):
                yield token

        self._emit(project_id, "agent_status", {"agent": "conversation", "status": "idle"})
        logger.info(f"Turn end: project={project_id}")

    # ── Planner task dispatch ────────────────────────────────────────────────

    # Matches PascalCase-looking identifiers ("Button", "PrimaryButton") in
    # free-text refactor requests like "rename Button to PrimaryButton" —
    # best-effort, since we have no AST/LSP-based symbol resolution (that's
    # out of scope; see the audit's Phase 5+ note). Every candidate found is
    # searched for, so both the old and new name's importers get included.
    _RENAME_SYMBOL_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*)\b")

    def _extract_rename_symbols(self, task: str) -> list[str]:
        return self._RENAME_SYMBOL_RE.findall(task)

    def _validate_tasks(self, raw_tasks: Any) -> list[dict]:
        """Return raw_tasks sorted by priority if it's a usable task list,
        otherwise an empty list (triggering the single-intent fallback)."""
        if not isinstance(raw_tasks, list) or not raw_tasks:
            return []
        valid = [
            t for t in raw_tasks
            if isinstance(t, dict) and t.get("agent") in KNOWN_TASK_AGENTS
        ]
        if not valid:
            return []
        return sorted(valid, key=lambda t: t.get("priority", 0))

    async def _execute_tasks(
        self,
        context: AgentContext,
        user_message: str,
        plan: dict,
        tasks: list[dict],
        message_id: str,
        force_apply: bool,
    ) -> AsyncIterator[str]:
        """Dispatch each planner task to its named agent, in priority order."""
        for subtask in tasks:
            agent_name = subtask["agent"]
            action = subtask.get("action") or user_message

            if agent_name == "codegen":
                async for token in self._handle_generation(
                    context, action, plan, message_id, emit_done=False, force_apply=force_apply
                ):
                    yield token
            elif agent_name in ("editing", "refactoring", "debug"):
                intent = _TASK_AGENT_TO_INTENT[agent_name]
                async for token in self._handle_editing(
                    context, action, plan, intent, message_id, emit_done=False, force_apply=force_apply
                ):
                    yield token
            elif agent_name == "search":
                async for token in self._run_search_task(context, action, message_id):
                    yield token
            elif agent_name == "repository":
                async for token in self._run_repository_task(context, message_id):
                    yield token
            elif agent_name == "review":
                # Review is already gated into every write in _handle_generation
                # / _handle_editing above; a standalone "review" task has no
                # files of its own to review, so it's a no-op here.
                continue

        self._emit(context.project_id, "stream_done", {"messageId": message_id})

    async def _run_search_task(self, context: AgentContext, action: str, message_id: str) -> AsyncIterator[str]:
        self._emit(context.project_id, "agent_status", {"agent": "search", "status": "working", "task": "Finding relevant files"})
        result = await self.search.run(action, context)
        files = result.data.get("files", [])
        self._emit(context.project_id, "agent_status", {"agent": "search", "status": "done"})

        summary = f"\n\nFound {len(files)} relevant file(s)"
        if files:
            summary += ": " + ", ".join(files[:10])
        summary += "\n"
        self._emit(context.project_id, "stream_token", {"token": summary, "messageId": message_id})
        yield summary

    async def _run_repository_task(self, context: AgentContext, message_id: str) -> AsyncIterator[str]:
        if not context.root_path:
            return
        self._emit(context.project_id, "agent_status", {"agent": "repository", "status": "working", "task": "Analyzing repository"})
        analysis = await self.analyze_repository(context.project_id, context.root_path, context.project_name)
        self._emit(context.project_id, "agent_status", {"agent": "repository", "status": "done"})

        summary = f"\n\n**Repository analysis:** {analysis.get('summary', 'complete')}\n"
        self._emit(context.project_id, "stream_token", {"token": summary, "messageId": message_id})
        yield summary

    # ── Review gate ──────────────────────────────────────────────────────────

    async def _review_files(
        self, context: AgentContext, task: str, files: list[dict]
    ) -> tuple[bool, str]:
        """Run ReviewAgent over proposed files before they're written. Returns
        (approved, message_for_user). message_for_user is only non-empty when
        the review rejected the change."""
        file_map = {f["path"]: f["content"] for f in files if f.get("path") and f.get("content")}
        if not file_map:
            return True, ""

        self._emit(context.project_id, "agent_status", {"agent": "review", "status": "working", "task": "Reviewing changes"})
        review_result = await self.review.run(task, context, files=file_map)
        self._emit(context.project_id, "agent_status", {"agent": "review", "status": "done"})

        data = review_result.data or {}
        approved = data.get("approved", True)
        score = data.get("score", 10)
        if approved and score >= settings.review_score_threshold:
            return True, ""

        issues = data.get("issues", [])
        lines = [f"\n\n⚠️ **Review flagged this change** (score {score}/10) — changes were **not** written."]
        for issue in issues[:8]:
            sev = issue.get("severity", "warning")
            loc = issue.get("file", "")
            lines.append(f"- [{sev}] {loc}: {issue.get('message', '')}")
        lines.append('\nAsk me to fix the issues, or say "apply anyway" to force it through.')
        return False, "\n".join(lines)

    # ── Memory ───────────────────────────────────────────────────────────────

    async def _update_memory(self, context: AgentContext, task: str, files: list[dict]) -> None:
        """Run MemoryAgent over what just changed and persist the merged
        result onto the project so the *next* turn's prompts include it."""
        if not context.project_id:
            return
        try:
            mem_result = await self.memory.run(
                task, context, recent_messages=context.conversation_history, generated_files=files
            )
            merged = mem_result.data or context.metadata
        except Exception as e:
            logger.warning(f"Memory agent failed: {e}")
            return

        if not merged:
            return

        context.metadata = merged
        try:
            # Orchestrator has no injected DB session (it's invoked from a
            # background task in routers/chat.py) — open a short-lived one,
            # same pattern already used by routers/upload.py's background
            # repository analysis.
            from app.database.database import AsyncSessionLocal
            from app.services import project_service

            async with AsyncSessionLocal() as session:
                await project_service.update_project(
                    session, context.project_id, metadata_json=json.dumps(merged)
                )
        except Exception as e:
            logger.warning(f"Failed to persist project memory: {e}")

    # ── Import repair ────────────────────────────────────────────────────────

    # Bounded so a model that keeps hallucinating new missing imports every
    # round can't loop forever.
    IMPORT_REPAIR_MAX_ROUNDS = 2

    async def _repair_missing_local_imports(
        self, context: AgentContext, task: str, touched_paths: list[str]
    ) -> None:
        """After files are written to disk (by generation or editing), check
        whichever files this turn touched for relative imports that don't
        resolve to anything in the project — e.g. BillingScreen.tsx
        importing './InvoiceTable' when no InvoiceTable.tsx was ever
        generated. This runs against real on-disk content and resolves
        against the *whole* project tree, not a possibly-incomplete
        pre-fetched snapshot (an earlier version of this lived inside
        EditingAgent operating on SearchAgent's limited `file_contents` and
        could silently miss the file being edited — see the fix's test
        coverage for the reproduction). If anything's missing, asks
        EditingAgent for exactly those files and writes them.
        """
        if not context.root_path or not touched_paths:
            return
        root = Path(context.root_path)
        remaining = touched_paths

        for _round in range(self.IMPORT_REPAIR_MAX_ROUNDS):
            if not remaining:
                return
            try:
                all_paths = {
                    str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()
                }
            except Exception:
                return

            touched_files = []
            for rel in remaining:
                try:
                    content, _ = file_service.read_file(root, rel)
                    touched_files.append({"path": rel, "content": content})
                except (FileNotFoundError, ValueError):
                    continue

            missing = find_missing_local_imports(touched_files, known_paths=all_paths)
            if not missing:
                return

            missing_lines = "\n".join(
                f'- "{m.resolved_hint}" (imported as "{m.specifier}" from {m.importer})' for m in missing[:15]
            )
            logger.warning(f"Post-write check found ungenerated files, repairing:\n{missing_lines}")

            repair_task = (
                "Generate exactly these missing files, which are already imported "
                f"elsewhere in the project, matching the style of the files shown:\n{missing_lines}"
            )
            repair_result = await self.editing.run(
                repair_task, context, file_contents={f["path"]: f["content"] for f in touched_files}
            )
            new_files = (repair_result.data or {}).get("new_files", []) if repair_result.success else []
            if not new_files:
                return

            written: list[str] = []
            async with self._get_write_lock(context.project_id):
                for f in new_files:
                    if not f.get("path") or not f.get("content"):
                        continue
                    try:
                        written_rel = file_service.write_generated_file(root, f["path"], f["content"])
                        written.append(written_rel)
                        self._emit(context.project_id, "file_created", {"path": written_rel})
                    except Exception as e:
                        logger.error(f"Failed writing repaired file {f.get('path')!r}: {e}")

            if not written:
                return
            # Newly-written files might themselves import something missing
            # — check those next round instead of re-scanning everything.
            remaining = written

    async def _handle_generation(
        self,
        context: AgentContext,
        task: str,
        plan: dict,
        message_id: str,
        emit_done: bool = True,
        force_apply: bool = False,
    ) -> AsyncIterator[str]:
        """Full project generation pipeline."""
        self._emit(context.project_id, "agent_status", {
            "agent": "codegen", "status": "thinking", "task": "Planning project structure"
        })

        # Stream the intro while generating
        async for token in self.codegen.stream(task, context, plan=plan):
            self._emit(context.project_id, "stream_token", {"token": token, "messageId": message_id})
            yield token

        # Actually generate files
        self._emit(context.project_id, "agent_status", {
            "agent": "codegen", "status": "working", "task": "Generating files"
        })
        gen_result = await self.codegen.run(task, context, plan=plan)

        if gen_result.success and gen_result.data.get("files"):
            files = gen_result.data["files"]

            if not force_apply:
                approved, review_msg = await self._review_files(context, task, files)
                if not approved:
                    self._emit(context.project_id, "stream_token", {"token": review_msg, "messageId": message_id})
                    yield review_msg
                    if emit_done:
                        self._emit(context.project_id, "stream_done", {"messageId": message_id})
                    return

            async with self._get_write_lock(context.project_id):
                written_paths = await self._write_files(context.root_path, files)

            await self._repair_missing_local_imports(context, task, written_paths)

            self._emit(context.project_id, "agent_status", {
                "agent": "git", "status": "working", "task": "Creating snapshot"
            })
            await self.git.run("snapshot", context, action="snapshot", changes=[f["path"] for f in files])

            self._emit(context.project_id, "agent_status", {
                "agent": "codegen", "status": "done"
            })

            summary = f"\n\n✅ **Generated {len(files)} files** successfully.\n"
            summary += "\n".join(f"- `{f['path']}`" for f in files[:10])
            if len(files) > 10:
                summary += f"\n- ...and {len(files) - 10} more files"

            self._emit(context.project_id, "stream_token", {"token": summary, "messageId": message_id})
            yield summary

            # Update file events
            for f in files:
                self._emit(context.project_id, "file_created", {"path": f["path"]})

            await self._update_memory(context, task, files)

        if emit_done:
            self._emit(context.project_id, "stream_done", {"messageId": message_id})

    async def _handle_editing(
        self,
        context: AgentContext,
        task: str,
        plan: dict,
        intent: str,
        message_id: str,
        emit_done: bool = True,
        force_apply: bool = False,
    ) -> AsyncIterator[str]:
        """Targeted editing pipeline."""
        # Search for relevant files
        self._emit(context.project_id, "agent_status", {
            "agent": "search", "status": "working", "task": "Finding relevant files"
        })
        search_kwargs: dict[str, Any] = {}
        if intent == "refactor":
            # A rename may span files that never mention the symbol by name
            # in their own filename/content in an obviously keyword-matchable
            # way (e.g. only via an aliased import) — the import-graph search
            # in SearchAgent catches those; a plain keyword search would not.
            symbols = self._extract_rename_symbols(task)
            if symbols:
                search_kwargs["symbols"] = symbols
        search_result = await self.search.run(task, context, **search_kwargs)
        relevant_files = search_result.data.get("files", [])

        self._emit(context.project_id, "agent_status", {"agent": "search", "status": "done"})

        # Read file contents
        file_contents: dict[str, str] = {}
        if context.root_path:
            root = Path(context.root_path)
            for rel_path in relevant_files[:8]:
                try:
                    content, _ = file_service.read_file(root, rel_path)
                    file_contents[rel_path] = content
                except (FileNotFoundError, ValueError):
                    pass

        self._emit(context.project_id, "agent_status", {
            "agent": "editing", "status": "working", "task": "Applying changes"
        })

        agent = self.debug if intent == "debug" else self.editing
        edit_result = await agent.run(task, context, file_contents=file_contents)

        intro = f"I'll {intent} the relevant files.\n\n"
        self._emit(context.project_id, "stream_token", {"token": intro, "messageId": message_id})
        yield intro

        if edit_result.success:
            content = await self._apply_edits(context, edit_result.data, task, force_apply=force_apply)
            self._emit(context.project_id, "stream_token", {"token": content, "messageId": message_id})
            yield content
        else:
            err = f"⚠️ Error: {edit_result.error}"
            self._emit(context.project_id, "stream_token", {"token": err, "messageId": message_id})
            yield err

        self._emit(context.project_id, "agent_status", {"agent": "editing", "status": "done"})
        if emit_done:
            self._emit(context.project_id, "stream_done", {"messageId": message_id})

    async def _handle_conversation(
        self, context: AgentContext, task: str, message_id: str
    ) -> AsyncIterator[str]:
        """Pure conversational response."""
        self._emit(context.project_id, "agent_status", {
            "agent": "conversation", "status": "thinking"
        })
        async for token in self.conversation.stream(task, context):
            self._emit(context.project_id, "stream_token", {"token": token, "messageId": message_id})
            yield token

        self._emit(context.project_id, "agent_status", {"agent": "conversation", "status": "done"})
        self._emit(context.project_id, "stream_done", {"messageId": message_id})

    # ── File writing (single code path — routes through file_service) ─────────

    async def _write_files(self, root_path: Optional[str], files: list[dict]) -> list[str]:
        """Write LLM-generated files. The only writer used by both the full
        generation pipeline and (via _apply_edits) the editing pipeline —
        goes through file_service.write_generated_file, which applies
        resolve_safe() containment and the src/-prefix normalization.
        Returns the relative paths actually written."""
        if not root_path:
            return []
        root = Path(root_path)
        written: list[str] = []
        for file_def in files:
            try:
                written.append(file_service.write_generated_file(root, file_def["path"], file_def["content"]))
            except ValueError as e:
                logger.error(f"Rejected unsafe path {file_def.get('path')!r}: {e}")
            except Exception as e:
                logger.error(f"Failed to write {file_def.get('path')!r}: {e}")
        return written

    async def _apply_edits(
        self, context: AgentContext, data: dict, task: str = "", force_apply: bool = False
    ) -> str:
        if not context.root_path:
            return "No project root configured."

        root = Path(context.root_path)

        proposed_files = list(data.get("files", [])) + list(data.get("new_files", []))
        if proposed_files and not force_apply:
            approved, review_msg = await self._review_files(context, task, proposed_files)
            if not approved:
                return review_msg

        # Held for the whole write phase (not just one file at a time) so a
        # second concurrent edit to this project can't interleave its own
        # writes with these.
        async with self._get_write_lock(context.project_id):
            applied, errors, written_paths = self._write_edit_operations(context, root, data)

        await self._repair_missing_local_imports(context, task, written_paths)

        result = ""
        if applied:
            result += "**Changes applied:**\n" + "\n".join(f"- {a}" for a in applied) + "\n"
        if errors:
            result += "\n**Issues:**\n" + "\n".join(f"- ⚠️ {e}" for e in errors)

        if applied:
            await self._update_memory(context, task, proposed_files)

        return result or "No changes were necessary."

    def _write_edit_operations(
        self, context: AgentContext, root: Path, data: dict
    ) -> tuple[list[str], list[str], list[str]]:
        """Apply every write/edit/delete in an EditingAgent/DebugAgent
        result. Must be called with the project's write lock held. Returns
        (applied_messages, error_messages, written_relative_paths)."""
        applied: list[str] = []
        errors: list[str] = []
        written: list[str] = []

        # Full-file rewrites — the fallback format, for changes substantial
        # enough that most of the file changes. When the agent hands back a
        # full rewrite for what turns out to be a small, localized change,
        # reduce it to a minimal search/replace before writing so the rest
        # of the file's formatting/whitespace stays byte-identical (see
        # file_service.minimal_edit_from_rewrite).
        for file_def in data.get("files", []):
            raw_rel = file_def.get("path", "")
            content = file_def.get("content", "")
            if not raw_rel or not content:
                continue
            rel = file_service.normalize_generated_path(raw_rel)
            try:
                original: Optional[str] = None
                try:
                    original, _ = file_service.read_file(root, rel)
                except (FileNotFoundError, ValueError):
                    original = None

                minimal = None
                if original is not None and not original.startswith("[Binary file"):
                    minimal = file_service.minimal_edit_from_rewrite(original, content)

                if minimal is not None:
                    search, replacement = minimal
                    file_service.write_file(root, rel, original.replace(search, replacement, 1))
                    applied.append(f"Updated `{rel}` (minimal patch)")
                else:
                    file_service.write_file(root, rel, content)
                    applied.append(f"Updated `{rel}`")
                written.append(rel)
                self._emit(context.project_id, "file_modified", {"path": rel})
            except Exception as e:
                errors.append(f"Error writing {rel}: {e}")

        # New files
        for file_def in data.get("new_files", []):
            rel = file_def.get("path", "")
            content = file_def.get("content", "")
            if not rel or not content:
                continue
            try:
                written_rel = file_service.write_generated_file(root, rel, content)
                applied.append(f"Created `{written_rel}`")
                written.append(written_rel)
                self._emit(context.project_id, "file_created", {"path": written_rel})
            except Exception as e:
                errors.append(f"Error creating {rel}: {e}")

        # Search/replace edits — the primary format for small, localized
        # changes (see EditingAgent's prompt). Kept alongside full-file
        # rewrites, which remain the fallback for substantial restructuring.
        for edit in data.get("edits", []):
            rel = edit.get("path", "")
            try:
                content, _ = file_service.read_file(root, rel)
            except FileNotFoundError:
                errors.append(f"File not found: {rel}")
                continue
            except ValueError as e:
                errors.append(f"Invalid path {rel}: {e}")
                continue
            try:
                search = edit.get("search", "")
                replacement = edit.get("replacement", "")
                if search and search in content:
                    file_service.write_file(root, rel, content.replace(search, replacement, 1))
                    applied.append(f"Patched `{rel}`")
                    written.append(rel)
                    self._emit(context.project_id, "file_modified", {"path": rel})
                else:
                    errors.append(f"Could not apply patch to `{rel}`")
            except Exception as e:
                errors.append(f"Error editing {rel}: {e}")

        # Deletions — "remove this component" requests delete the file
        # instead of just editing its content down to nothing.
        for rel in data.get("deletions", []):
            if not rel:
                continue
            try:
                file_service.delete_file(root, rel)
                applied.append(f"Deleted `{rel}`")
                self._emit(context.project_id, "file_deleted", {"path": rel})
            except FileNotFoundError:
                errors.append(f"Could not delete {rel}: file not found")
            except ValueError as e:
                errors.append(f"Invalid path {rel}: {e}")
            except Exception as e:
                errors.append(f"Error deleting {rel}: {e}")

        return applied, errors, written

    async def analyze_repository(self, project_id: str, root_path: str, project_name: str) -> dict:
        """Analyze an uploaded repository and extract metadata."""
        root = Path(root_path)
        context = AgentContext(project_id=project_id, project_name=project_name, root_path=root_path)

        # Build file tree string
        file_tree = self._build_file_tree_str(root)

        # Read key files
        key_files: dict[str, str] = {}
        priority_files = [
            "package.json", "tsconfig.json", "vite.config.ts", "next.config.js",
            "tailwind.config.ts", "tailwind.config.js", "src/App.tsx", "src/main.tsx",
            "src/index.tsx", "app/layout.tsx", "pages/_app.tsx",
        ]
        for filename in priority_files:
            full = root / filename
            if full.exists():
                try:
                    key_files[filename] = full.read_text(encoding="utf-8", errors="replace")[:3000]
                except Exception:
                    pass

        result = await self.repository.run("Analyze project", context, file_tree=file_tree, key_files=key_files)
        return result.data

    def _build_file_tree_str(self, root: Path, max_files: int = 200) -> str:
        ignore = {"node_modules", "dist", "build", ".cache", ".git", "__pycache__", ".next"}
        lines: list[str] = []
        count = 0

        def walk(path: Path, prefix: str = "") -> None:
            nonlocal count
            if count >= max_files:
                return
            entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
            for entry in entries:
                if entry.name in ignore or entry.name.startswith("."):
                    continue
                lines.append(f"{prefix}{'📁' if entry.is_dir() else '📄'} {entry.name}")
                count += 1
                if entry.is_dir() and count < max_files:
                    walk(entry, prefix + "  ")

        walk(root)
        return "\n".join(lines)


# Singleton
orchestrator = Orchestrator()
