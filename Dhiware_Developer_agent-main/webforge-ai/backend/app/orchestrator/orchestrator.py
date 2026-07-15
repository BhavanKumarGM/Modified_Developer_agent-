"""
Central Orchestrator — routes tasks to agents, manages pipeline execution,
broadcasts events over WebSocket.
"""
from __future__ import annotations

import asyncio
import json
import uuid
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

import logging

logger = logging.getLogger(__name__)


EventCallback = Callable[[str, dict], None]


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
        context = AgentContext(
            project_id=project_id,
            project_name=project_name,
            framework=framework,
            root_path=root_path,
            metadata=metadata,
            conversation_history=conversation_history,
        )

        self._emit(project_id, "agent_status", {"agent": "planner", "status": "thinking", "task": "Analyzing request"})

        # 1. Plan
        plan_result = await self.planner.run(user_message, context)
        plan = plan_result.data
        intent = plan.get("intent", "build")

        self._emit(project_id, "agent_status", {"agent": "planner", "status": "done", "task": None})

        # 2. Dispatch based on intent
        if intent in ("build",) and plan.get("requires_full_generation"):
            async for token in self._handle_generation(context, user_message, plan, message_id):
                yield token
        elif intent in ("edit", "refactor", "debug"):
            async for token in self._handle_editing(context, user_message, plan, intent, message_id):
                yield token
        else:
            # Conversation / explain / analyze
            async for token in self._handle_conversation(context, user_message, message_id):
                yield token

        self._emit(project_id, "agent_status", {"agent": "conversation", "status": "idle"})

    async def _handle_generation(
        self, context: AgentContext, task: str, plan: dict, message_id: str
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
            await self._write_files(context.root_path, files)

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

        self._emit(context.project_id, "stream_done", {"messageId": message_id})

    async def _handle_editing(
        self, context: AgentContext, task: str, plan: dict, intent: str, message_id: str
    ) -> AsyncIterator[str]:
        """Targeted editing pipeline."""
        # Search for relevant files
        self._emit(context.project_id, "agent_status", {
            "agent": "search", "status": "working", "task": "Finding relevant files"
        })
        search_result = await self.search.run(task, context)
        relevant_files = search_result.data.get("files", [])

        self._emit(context.project_id, "agent_status", {"agent": "search", "status": "done"})

        # Read file contents
        file_contents: dict[str, str] = {}
        if context.root_path:
            root = Path(context.root_path)
            for rel_path in relevant_files[:8]:
                full = root / rel_path
                if full.exists() and full.is_file():
                    try:
                        file_contents[rel_path] = full.read_text(encoding="utf-8", errors="replace")
                    except Exception:
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
            content = await self._apply_edits(context, edit_result.data)
            self._emit(context.project_id, "stream_token", {"token": content, "messageId": message_id})
            yield content
        else:
            err = f"⚠️ Error: {edit_result.error}"
            self._emit(context.project_id, "stream_token", {"token": err, "messageId": message_id})
            yield err

        self._emit(context.project_id, "agent_status", {"agent": "editing", "status": "done"})
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

    # Source files that belong under src/ but LLM sometimes puts in root
    _SRC_FILES = {"App.tsx", "App.jsx", "App.ts", "index.css", "global.css",
                  "globals.css", "App.css", "main.tsx", "main.jsx"}

    async def _write_files(self, root_path: Optional[str], files: list[dict]) -> None:
        if not root_path:
            return
        root = Path(root_path)
        for file_def in files:
            rel = file_def["path"].lstrip("/").replace("\\", "/")

            # Normalise: if LLM omitted src/ prefix on source files, add it
            filename = rel.split("/")[-1]
            if "/" not in rel and filename in self._SRC_FILES:
                rel = f"src/{filename}"

            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                path.write_text(file_def["content"], encoding="utf-8")
            except Exception as e:
                logger.error(f"Failed to write {rel}: {e}")

    async def _apply_edits(self, context: AgentContext, data: dict) -> str:
        if not context.root_path:
            return "No project root configured."

        root = Path(context.root_path)
        applied: list[str] = []
        errors: list[str] = []

        # Full-file rewrites (primary editing format)
        for file_def in data.get("files", []):
            rel = file_def.get("path", "").lstrip("/").replace("\\", "/")
            content = file_def.get("content", "")
            if not rel or not content:
                continue
            try:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                applied.append(f"Updated `{rel}`")
                self._emit(context.project_id, "file_modified", {"path": rel})
            except Exception as e:
                errors.append(f"Error writing {rel}: {e}")

        # New files
        for file_def in data.get("new_files", []):
            rel = file_def.get("path", "").lstrip("/").replace("\\", "/")
            content = file_def.get("content", "")
            if not rel or not content:
                continue
            try:
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                applied.append(f"Created `{rel}`")
                self._emit(context.project_id, "file_created", {"path": rel})
            except Exception as e:
                errors.append(f"Error creating {rel}: {e}")

        # Legacy search-replace edits (kept for backwards compatibility)
        for edit in data.get("edits", []):
            file_path = root / edit["path"]
            if not file_path.exists():
                errors.append(f"File not found: {edit['path']}")
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                search = edit.get("search", "")
                replacement = edit.get("replacement", "")
                if search and search in content:
                    file_path.write_text(content.replace(search, replacement, 1), encoding="utf-8")
                    applied.append(f"Patched `{edit['path']}`")
                    self._emit(context.project_id, "file_modified", {"path": edit["path"]})
                else:
                    errors.append(f"Could not apply patch to `{edit['path']}`")
            except Exception as e:
                errors.append(f"Error editing {edit['path']}: {e}")

        result = ""
        if applied:
            result += "**Changes applied:**\n" + "\n".join(f"- {a}" for a in applied) + "\n"
        if errors:
            result += "\n**Issues:**\n" + "\n".join(f"- ⚠️ {e}" for e in errors)

        return result or "No changes were necessary."

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
