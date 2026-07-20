"""Maintains project memory: theme, conventions, preferences."""
from __future__ import annotations

import json
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService


SYSTEM_PROMPT = """You are the Memory Agent for WebForge AI.

Extract and update project memory from conversations and code changes.

Output ONLY valid JSON representing memory updates:
{
  "theme": "dark|light|auto",
  "primary_color": "#6366f1",
  "architecture": "spa|feature-based|atomic-design",
  "styling": ["tailwind"],
  "naming_convention": "camelCase",
  "folder_structure": "feature-based",
  "preferred_libraries": ["zustand", "react-query"],
  "component_style": "functional-hooks",
  "updates": ["list of what changed"]
}

Only include fields that are explicitly mentioned or clearly inferable.
"""


class MemoryAgent(BaseAgent):
    name = "memory"
    description = "Remembers and updates project conventions, theme, and preferences"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)
        recent_messages = kwargs.get("recent_messages", [])
        generated_files = kwargs.get("generated_files", [])

        sample_code = ""
        if generated_files:
            # Sample first file for style analysis
            first_file = generated_files[0] if isinstance(generated_files[0], dict) else {}
            sample_code = first_file.get("content", "")[:1000]

        prompt = f"""
Analyze this interaction and extract memory updates:

User request: {task}

Recent conversation: {json.dumps(recent_messages[-3:] if recent_messages else [])}

Sample generated code:
{sample_code}

Current memory: {json.dumps(context.metadata)}

What memory should be updated? Output JSON only.
"""
        request = self._build_request(
            system=SYSTEM_PROMPT,
            user=prompt,
            temperature=0.1,
        )
        response = await self.llm.generate(request)

        try:
            updates = self._extract_json(response.content)
            merged = {**context.metadata, **updates}
            return AgentResult(success=True, content="Memory updated", data=merged)
        except Exception:
            return AgentResult(success=True, content="No memory updates", data=context.metadata)
