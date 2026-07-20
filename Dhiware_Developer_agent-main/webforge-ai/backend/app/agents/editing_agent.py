"""Modifies existing code with minimal, targeted patches."""
from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService


SYSTEM_PROMPT = """You are the Editing Agent for WebForge AI.

You modify existing source files to fulfil the user's request.

Output ONLY valid JSON (no markdown, no explanation outside the JSON):
{
  "edits": [
    {
      "path": "src/App.tsx",
      "search": "the exact existing code to find — copy it verbatim from the file shown below, including whitespace",
      "replacement": "the replacement code for that exact span"
    }
  ],
  "files": [
    {
      "path": "src/App.tsx",
      "content": "COMPLETE updated file — every single line, nothing omitted or truncated"
    }
  ],
  "new_files": [
    { "path": "src/components/NewThing.tsx", "content": "..." }
  ],
  "deletions": ["src/components/Obsolete.tsx"],
  "description": "what was changed"
}

STRICT RULES:
1. You may ONLY edit files that appear in the "Existing files" section below. New files go in "new_files".
2. PREFER "edits" (search/replace) for small, localized changes — a single function, a JSX block, a style tweak, a copy change. This is the primary format: it leaves the rest of the file untouched.
3. Only use "files" (a full-file rewrite) when the change is substantial enough that most of the file's lines actually change — e.g. restructuring a component.
4. "search" must be an exact, minimal, uniquely-matching substring of the current file content — copy it verbatim, do not paraphrase, reformat, or re-indent it.
5. If you do use "files", put the FULL updated content in "content" — never use "..." or truncate.
6. If the user asks to remove/delete a component or file entirely, put its path in "deletions" — do not just empty out its content.
7. If you add an import of a sibling component/module that doesn't already exist in "Existing files", you MUST also generate it in "new_files" — never import something you didn't create.
8. Escape all special characters properly for JSON: newlines as \\n, quotes as \\".
9. Output ONLY the JSON object. Start your response with { and end with }.
"""


class EditingAgent(BaseAgent):
    name = "editing"
    description = "Modifies existing code with minimal, targeted patches"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        file_contents = kwargs.get("file_contents", {})

        files_context = "\n\n".join(
            f"File: {path}\n```\n{content}\n```"
            for path, content in file_contents.items()
        )

        memory_section = self._format_memory(context.metadata)

        prompt = f"""Task: {task}

Project: {context.project_name} ({context.framework})
{memory_section}
Current file contents (read carefully before editing):
{files_context}

Prefer "edits" (search/replace) for localized changes; only use "files" for
substantial rewrites. Output JSON only."""
        request = self._build_request(
            system=SYSTEM_PROMPT,
            user=prompt,
            temperature=0.2,
        )
        response = await self.llm.generate(request)

        try:
            data = self._extract_json(response.content)
            paths = (
                [e["path"] for e in data.get("edits", [])]
                + [f["path"] for f in data.get("files", [])]
                + [f["path"] for f in data.get("new_files", [])]
            )
            return AgentResult(success=True, content=data.get("description", ""), data=data, files_modified=paths)
        except Exception as e:
            return AgentResult(success=False, error=str(e), content=response.content)
