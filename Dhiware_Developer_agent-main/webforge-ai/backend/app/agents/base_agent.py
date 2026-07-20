"""Base class for all WebForge agents."""
from __future__ import annotations

import json
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

    _MEMORY_FIELDS = {
        "theme", "primary_color", "architecture", "styling",
        "naming_convention", "folder_structure", "preferred_libraries",
        "component_style",
    }

    def _format_memory(self, metadata: dict) -> str:
        """Render project memory (theme, naming convention, preferred libs,
        ...) as a prompt section, so generation/editing stays stylistically
        consistent with what MemoryAgent established on earlier turns. Empty
        when there is no memory yet (e.g. the project's first turn)."""
        if not metadata:
            return ""
        relevant = {k: v for k, v in metadata.items() if k in self._MEMORY_FIELDS and v}
        if not relevant:
            return ""
        return (
            "\nProject conventions established so far (stay consistent with these):\n"
            f"{json.dumps(relevant, indent=2)}\n"
        )

    # ── JSON extraction ──────────────────────────────────────────────────
    # The single implementation every agent uses to pull a JSON object out
    # of raw LLM output. Do not add another copy of this in an agent — route
    # through here so every agent gets the same (tested) parsing behavior.

    def _extract_json(self, text: str) -> dict:
        """Extract the first top-level JSON object from LLM output.

        Scans for each '{' and attempts `json.JSONDecoder.raw_decode` from
        that position — unlike a greedy regex, `raw_decode` stops exactly at
        the matching close brace, so it doesn't over-match on stray braces
        appearing in surrounding prose. If every attempt fails (typically
        because the LLM left literal newlines/tabs inside a JSON string
        value, which is invalid JSON), falls back to manually locating the
        balanced-brace span and repairing those characters before retrying.
        """
        text = text.strip()
        decoder = json.JSONDecoder()

        for idx, ch in enumerate(text):
            if ch != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(text, idx)
                return obj
            except json.JSONDecodeError:
                continue

        span = self._find_balanced_brace_span(text)
        if span is None:
            raise ValueError("No JSON object found in response")
        start, end = span
        repaired = self._repair_json_strings(text[start:end])
        return json.loads(repaired)

    @staticmethod
    def _find_balanced_brace_span(text: str) -> Optional[tuple[int, int]]:
        """Return (start, end) of the first balanced {...} span, respecting
        string boundaries so braces inside string values don't miscount."""
        start = text.find("{")
        if start == -1:
            return None

        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return start, i + 1
        return None

    @staticmethod
    def _repair_json_strings(text: str) -> str:
        """Replace literal newlines/tabs inside JSON string values with
        proper escape sequences (LLMs frequently emit these, producing
        invalid-but-fixable JSON)."""
        result = []
        in_string = False
        escape_next = False
        for ch in text:
            if escape_next:
                result.append(ch)
                escape_next = False
                continue
            if ch == "\\" and in_string:
                result.append(ch)
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == "\n":
                    result.append("\\n")
                elif ch == "\r":
                    result.append("\\r")
                elif ch == "\t":
                    result.append("\\t")
                else:
                    result.append(ch)
            else:
                result.append(ch)
        return "".join(result)
