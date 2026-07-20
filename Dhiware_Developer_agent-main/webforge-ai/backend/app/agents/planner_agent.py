"""Understands user intent and breaks requests into ordered subtasks."""
from __future__ import annotations

import json
from typing import Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService


SYSTEM_PROMPT = """You are the Planner Agent for WebForge AI.

Your role: Analyze user requests and produce a structured execution plan.

Output ONLY valid JSON with this shape:
{
  "intent": "build|edit|refactor|debug|analyze|explain",
  "summary": "Brief description of what will be done",
  "tasks": [
    {
      "agent": "codegen|editing|refactoring|debug|review|repository|search",
      "action": "specific action description",
      "files": ["optional list of target files"],
      "priority": 1
    }
  ],
  "requires_full_generation": false
}

Rules:
- "build" intent with a new project → requires_full_generation: true
- "edit" → target specific files, never regenerate entire project
- Order tasks by dependency (lower priority number = runs first)
- Keep tasks atomic and specific
"""


class PlannerAgent(BaseAgent):
    name = "planner"
    description = "Understands user intent and breaks requests into subtasks"

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        self._log_task(task)

        user_prompt = f"""
Project: {context.project_name} ({context.framework})
Framework metadata: {json.dumps(context.metadata, indent=2)}

User request: {task}

Produce a JSON execution plan.
"""
        request = self._build_request(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.2,
        )
        response = await self.llm.generate(request)

        try:
            plan = self._extract_json(response.content)
            return AgentResult(success=True, content=response.content, data=plan)
        except Exception as e:
            self.logger.warning(f"Failed to parse plan JSON: {e}")
            return AgentResult(
                success=True,
                content=response.content,
                data={
                    "intent": "build",
                    "summary": task,
                    "tasks": [{"agent": "codegen", "action": task, "priority": 1}],
                    "requires_full_generation": True,
                },
            )
