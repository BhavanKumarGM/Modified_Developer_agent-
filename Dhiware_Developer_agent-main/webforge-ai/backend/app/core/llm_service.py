"""
LLM Abstraction Layer — the single point of contact between agents and Ollama.
NO agent should call Ollama directly. All inference goes through this service.
"""
from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field

import httpx

from app.core.config import settings


@dataclass
class LLMMessage:
    role: str  # system | user | assistant
    content: str


@dataclass
class LLMRequest:
    messages: list[LLMMessage]
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    system: Optional[str] = None
    stream: bool = True


@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    done: bool = True


class LLMService:
    """
    Unified abstraction over Ollama. All agents use this — never httpx directly.
    """

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation. Returns complete response."""
        model = request.model or settings.default_model
        messages = self._build_messages(request)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": request.temperature},
        }
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens

        resp = await self._client.post("/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

        return LLMResponse(
            content=data["message"]["content"],
            model=data.get("model", model),
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Streaming generation. Yields tokens as they arrive."""
        model = request.model or settings.default_model
        messages = self._build_messages(request)

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": request.temperature},
        }
        if request.max_tokens:
            payload["options"]["num_predict"] = request.max_tokens

        async with self._client.stream("POST", "/api/chat", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

    async def list_models(self) -> list[str]:
        try:
            resp = await self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get("/")
            return resp.status_code == 200
        except Exception:
            return False

    def _build_messages(self, request: LLMRequest) -> list[dict]:
        messages = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        for msg in request.messages:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    async def close(self) -> None:
        await self._client.aclose()


# Singleton used throughout the app
llm_service = LLMService()
