"""Reads errors, stack traces, and console logs to diagnose and fix issues."""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult


SYSTEM_PROMPT = """You are the Debug Agent for WebForge AI.

Analyze errors, stack traces, and build logs to diagnose and fix issues.

Output ONLY valid JSON:
{
  "root_cause": "Description of the root cause",
  "affected_files": ["src/App.tsx"],
  "fixes": [
    {
      "path": "src/App.tsx",
      "search": "exact problematic code",
      "replacement": "fixed code",
      "explanation": "why this fixes it"
    }
  ],
  "new_files": [],
  "explanation": "Full explanation for the user"
}
"""


class DebugAgent(BaseAgent):
    name = "debug"
    description = "Diagnoses errors and stack traces, automatically fixes issues"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        error_log = kwargs.get("error_log", "")
        file_contents = kwargs.get("file_contents", {})

        files_str = "\n\n".join(
            f"=== {path} ===\n```\n{content[:2000]}\n```"
            for path, content in file_contents.items()
        )

        prompt = f"""
Debug this error:

Error log:
{error_log}

Related files:
{files_str}

User context: {task}

Diagnose the root cause and provide specific fixes. Output JSON only.
"""
        request = self._build_request(
            system=SYSTEM_PROMPT,
            user=prompt,
            temperature=0.2,
        )
        response = await self.llm.generate(request)

        try:
            data = self._extract_json(response.content)
            return AgentResult(
                success=True,
                content=data.get("explanation", ""),
                data=data,
                files_modified=data.get("affected_files", []),
            )
        except Exception as e:
            return AgentResult(success=False, error=str(e), content=response.content)

    def _extract_json(self, text: str) -> dict:
        match = re.search(r'\{[\s\S]+\}', text)
        if match:
            return json.loads(match.group())
        raise ValueError("No JSON found")
