"""Modifies existing code with minimal, targeted patches."""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService


SYSTEM_PROMPT = """You are the Editing Agent for WebForge AI.

You modify existing source files to fulfil the user's request.

Output ONLY valid JSON (no markdown, no explanation outside the JSON):
{
  "files": [
    {
      "path": "src/App.tsx",
      "content": "COMPLETE updated file — every single line, nothing omitted or truncated"
    }
  ],
  "new_files": [],
  "description": "what was changed"
}

STRICT RULES:
1. You may ONLY edit files that appear in the "Existing files" section below.
2. Never invent or create a file whose path was not shown to you.
3. Put the FULL updated content in "content" — never use "..." or truncate.
4. Escape all special characters properly for JSON: newlines as \\n, quotes as \\".
5. Only include files that actually change. Leave unchanged files out.
6. Output ONLY the JSON object. Start your response with { and end with }.
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

        prompt = f"""Task: {task}

Project: {context.project_name} ({context.framework})

Current file contents (read carefully before rewriting):
{files_context}

Return the full updated content of every file you change in the "files" array.
Output JSON only."""
        request = self._build_request(
            system=SYSTEM_PROMPT,
            user=prompt,
            temperature=0.2,
        )
        response = await self.llm.generate(request)

        try:
            data = self._extract_json(response.content)
            paths = [e["path"] for e in data.get("edits", [])] + [f["path"] for f in data.get("new_files", [])]
            return AgentResult(success=True, content=data.get("description", ""), data=data, files_modified=paths)
        except Exception as e:
            return AgentResult(success=False, error=str(e), content=response.content)

    def _extract_json(self, text: str) -> dict:
        match = re.search(r'\{[\s\S]+\}', text)
        if not match:
            raise ValueError("No JSON found")
        raw = match.group()
        # Try strict parse first
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
        # Repair: the LLM often puts literal newlines inside JSON string values.
        # Replace unescaped newlines/tabs inside string literals only.
        repaired = self._repair_json_strings(raw)
        return json.loads(repaired)

    @staticmethod
    def _repair_json_strings(text: str) -> str:
        """Replace literal newlines/tabs inside JSON string values with escape sequences."""
        result = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == '\\' and in_string:
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == '\n':
                    result.append('\\n')
                elif ch == '\r':
                    result.append('\\r')
                elif ch == '\t':
                    result.append('\\t')
                else:
                    result.append(ch)
            else:
                result.append(ch)
        return ''.join(result)
