"""Base class for all WebForge agents."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Optional

from app.core.llm_service import LLMService, LLMRequest, LLMMessage

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    project_id: str
    project_name: str
    framework: str = "unknown"
    root_path: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    conversation_history: list[dict] = field(default_factory=list)


@dataclass
class AgentResult:
    success: bool
    content: str = ""
    data: dict = field(default_factory=dict)
    files_modified: list[str] = field(default_factory=list)
    error: Optional[str] = None


class BaseAgent(ABC):
    name: str = "base"
    description: str = ""

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm
        self.logger = logging.getLogger(f"agent.{self.name}")

    @abstractmethod
    async def run(self, task: str, context: AgentContext, **kwargs: Any) -> AgentResult:
        """Execute the agent's main task."""
        ...

    async def stream(self, task: str, context: AgentContext, **kwargs: Any) -> AsyncIterator[str]:
        """Stream response tokens. Override for streaming-capable agents."""
        result = await self.run(task, context, **kwargs)
        yield result.content

    def _build_request(
        self,
        system: str,
        user: str,
        history: Optional[list[dict]] = None,
        temperature: float = 0.7,
    ) -> LLMRequest:
        messages = []
        if history:
            for msg in history[-10:]:  # Keep last 10 turns for context
                messages.append(LLMMessage(role=msg["role"], content=msg["content"]))
        messages.append(LLMMessage(role="user", content=user))
        return LLMRequest(messages=messages, system=system, temperature=temperature)

    def _log_task(self, task: str) -> None:
        self.logger.info(f"[{self.name}] Task: {task[:100]}")
