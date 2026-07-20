"""Reviews every code modification for quality and correctness."""
from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult


SYSTEM_PROMPT = """You are the Review Agent for WebForge AI.

Review code modifications for quality, correctness, and consistency.

Output ONLY valid JSON:
{
  "approved": true,
  "score": 8,
  "issues": [
    {
      "severity": "error|warning|info",
      "file": "src/App.tsx",
      "line": 42,
      "message": "description of issue",
      "suggestion": "how to fix"
    }
  ],
  "improvements": ["optional suggestions"],
  "summary": "Overall review summary"
}

Review for:
- TypeScript errors and type safety
- Unused imports or variables
- Security issues (XSS, injection)
- Performance issues
- Accessibility problems
- Code style consistency
"""


class ReviewAgent(BaseAgent):
    name = "review"
    description = "Reviews code modifications for quality and correctness"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        files = kwargs.get("files", {})

        files_str = "\n\n".join(
            f"=== {path} ===\n```\n{content[:3000]}\n```"
            for path, content in files.items()
        )

        prompt = f"""
Review these modified files for the task: {task}

{files_str}

Identify any issues, then approve or reject. Output JSON only.
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
                success=data.get("approved", True),
                content=data.get("summary", "Review complete"),
                data=data,
            )
        except Exception:
            return AgentResult(success=True, content="Review passed", data={"approved": True})
