"""Manages conversation flow, streaming responses, and context maintenance."""
from __future__ import annotations

from typing import AsyncIterator, Any

from app.agents.base_agent import BaseAgent, AgentContext, AgentResult
from app.core.llm_service import LLMService


SYSTEM_PROMPT = """You are WebForge AI — a senior software engineering assistant specializing in building and editing web applications.

You help users:
- Build complete websites from natural language descriptions
- Analyze and understand existing codebases
- Edit, refactor, debug, and optimize code
- Explain architecture and suggest improvements

Current project: {project_name} ({framework})

Guidelines:
- Be concise and technical. Don't over-explain unless asked.
- When generating code, use the project's existing conventions ({framework}, TypeScript if applicable).
- When you plan to make changes, briefly describe what you'll do, then proceed.
- Reference specific files and line numbers when relevant.
- Never make up information about files you haven't read.
"""


class ConversationAgent(BaseAgent):
    name = "conversation"
    description = "Manages conversation flow, streams responses, maintains context"

    def __init__(self, llm: LLMService) -> None:
        super().__init__(llm)

    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        request = self._build_request(
            system=SYSTEM_PROMPT.format(
                project_name=context.project_name,
                framework=context.framework,
            ),
            user=task,
            history=context.conversation_history,
            temperature=0.7,
        )
        response = await self.llm.generate(request)
        return AgentResult(success=True, content=response.content)

    async def stream(self, task: str, context: AgentContext, **kwargs: Any) -> AsyncIterator[str]:
        request = self._build_request(
            system=SYSTEM_PROMPT.format(
                project_name=context.project_name,
                framework=context.framework,
            ),
            user=task,
            history=context.conversation_history,
            temperature=0.7,
        )
        async for token in self.llm.stream(request):
            yield token
