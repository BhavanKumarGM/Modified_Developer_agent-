"""
LLM Abstraction Layer — the single point of contact between agents and Ollama.
NO agent should call Ollama directly. All inference goes through this service.
"""
from __future__ import annotations

import asyncio
import json
import random
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

# Errors worth retrying: Ollama not up yet, connection reset, request timed
# out. A 4xx from Ollama means the request itself is bad (wrong model name,
# malformed payload) — retrying it would just fail the same way three times.
_RETRYABLE_EXCEPTIONS = (httpx.ConnectError, httpx.TimeoutException, httpx.ReadError)


def model_name_matches(target: str, available: list[str]) -> bool:
    """True if `target` (e.g. settings.default_model) is present in
    `available` (as returned by LLMService.list_models()).

    Ollama's /api/tags always returns fully-tagged names (e.g.
    "nomic-embed-text:latest"), but a config value is often left untagged
    (e.g. "nomic-embed-text") — in that case a bare name matches any tag of
    that same model.
    """
    if target in available:
        return True
    if ":" not in target:
        return any(m == target or m.startswith(f"{target}:") for m in available)
    return False


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

    def __init__(self, max_retries: int = 2, base_backoff: float = 0.5) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )
        self.max_retries = max_retries
        self.base_backoff = base_backoff

    def _backoff_delay(self, attempt: int) -> float:
        """Exponential backoff with jitter: attempt 1 -> ~[0.5, 0.75)s,
        attempt 2 -> ~[1.0, 1.25)s, etc."""
        return (self.base_backoff * (2 ** (attempt - 1))) + random.uniform(0, self.base_backoff * 0.5)

    def _is_retryable_status(self, exc: httpx.HTTPStatusError) -> bool:
        status = exc.response.status_code if exc.response is not None else 0
        return not (400 <= status < 500)  # retry 5xx/0, not 4xx

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming generation. Returns complete response. Retries on
        connection errors/timeouts (not on 4xx) with exponential backoff."""
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

        attempt = 0
        while True:
            try:
                resp = await self._client.post("/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                return LLMResponse(
                    content=data["message"]["content"],
                    model=data.get("model", model),
                    prompt_tokens=data.get("prompt_eval_count", 0),
                    completion_tokens=data.get("eval_count", 0),
                )
            except httpx.HTTPStatusError as e:
                if not self._is_retryable_status(e) or attempt >= self.max_retries:
                    raise
            except _RETRYABLE_EXCEPTIONS:
                if attempt >= self.max_retries:
                    raise
            attempt += 1
            await asyncio.sleep(self._backoff_delay(attempt))

    async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
        """Streaming generation. Yields tokens as they arrive.

        Retries (with backoff) apply only to establishing the stream — once
        at least one token has been yielded, a failure is raised rather than
        silently restarting, since re-running the request would duplicate
        output already sent to the caller.
        """
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

        attempt = 0
        while True:
            started = False
            try:
                async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            started = True
                            yield token
                        if chunk.get("done"):
                            return
                return
            except httpx.HTTPStatusError as e:
                if started or not self._is_retryable_status(e) or attempt >= self.max_retries:
                    raise
            except _RETRYABLE_EXCEPTIONS:
                if started or attempt >= self.max_retries:
                    raise
            attempt += 1
            await asyncio.sleep(self._backoff_delay(attempt))

    async def embed(self, text: str, model: Optional[str] = None) -> list[float]:
        """Local embedding via Ollama's /api/embeddings — the only path
        SearchAgent's semantic index uses; it never calls Ollama directly."""
        resp = await self._client.post(
            "/api/embeddings",
            json={"model": model or settings.embedding_model, "prompt": text},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["embedding"]

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
