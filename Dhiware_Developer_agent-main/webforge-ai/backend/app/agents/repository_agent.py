"""Analyzes uploaded repositories to understand their structure and architecture."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService


SYSTEM_PROMPT = """You are the Repository Analysis Agent for WebForge AI.

Analyze the provided project structure and files to build a complete understanding.

Output ONLY valid JSON:
{
  "framework": "react|nextjs|vue|angular|static|unknown",
  "language": "typescript|javascript",
  "styling": ["tailwind", "css-modules", "styled-components", "plain-css"],
  "routing": "react-router|next-router|vue-router|none",
  "state_management": "zustand|redux|context|none",
  "has_typescript": true,
  "has_tests": false,
  "architecture": "spa|ssr|static|fullstack",
  "naming_convention": "camelCase|PascalCase|kebab-case",
  "folder_structure": "feature-based|type-based|mixed",
  "dependencies": ["key dependencies"],
  "entry_points": ["src/main.tsx", "src/App.tsx"],
  "pages": ["list of page files"],
  "components": ["list of component files"],
  "hooks": ["list of custom hooks"],
  "api_layer": "axios|fetch|none",
  "summary": "Brief human-readable summary of the project"
}
"""


class RepositoryAgent(BaseAgent):
    name = "repository"
    description = "Analyzes project structure, detects framework, builds understanding"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        file_tree = kwargs.get("file_tree", "")
        key_files = kwargs.get("key_files", {})

        key_files_str = "\n\n".join(
            f"=== {path} ===\n{content[:2000]}"  # Limit per file
            for path, content in list(key_files.items())[:10]
        )

        prompt = f"""
Analyze this project:

File tree:
{file_tree}

Key files:
{key_files_str}

Determine the framework, architecture, and conventions. Output JSON only.
"""
        request = self._build_request(
            system=SYSTEM_PROMPT,
            user=prompt,
            temperature=0.1,
        )
        response = await self.llm.generate(request)

        try:
            data = self._extract_json(response.content)
            return AgentResult(success=True, content=data.get("summary", ""), data=data)
        except Exception as e:
            return AgentResult(success=False, error=str(e), content=response.content)
