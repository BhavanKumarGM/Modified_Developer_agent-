"""Regression tests for audit item 4.1: LLMService.generate/.stream must
retry transient Ollama failures (connection errors, timeouts, 5xx) with
backoff, and must NOT retry 4xx (a genuinely bad request).
"""
import httpx
import pytest

from app.core.llm_service import LLMMessage, LLMRequest, LLMService


def _request() -> LLMRequest:
    return LLMRequest(messages=[LLMMessage(role="user", content="hi")])


def _ok_response(content: str = "hello") -> httpx.Response:
    return httpx.Response(
        200,
        json={"message": {"content": content}, "model": "test-model", "prompt_eval_count": 1, "eval_count": 2},
        request=httpx.Request("POST", "http://x/api/chat"),
    )


@pytest.fixture()
def llm():
    service = LLMService(max_retries=2, base_backoff=0.001)
    return service


async def test_generate_retries_transient_failures_then_succeeds(llm, monkeypatch):
    calls = {"n": 0}

    async def fake_post(path, json):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise httpx.ConnectError("connection refused", request=httpx.Request("POST", "http://x"))
        return _ok_response("recovered")

    monkeypatch.setattr(llm._client, "post", fake_post)

    result = await llm.generate(_request())

    assert result.content == "recovered"
    assert calls["n"] == 3  # 2 failures + 1 success = matches max_retries=2


async def test_generate_gives_up_after_max_retries(llm, monkeypatch):
    calls = {"n": 0}

    async def fake_post(path, json):
        calls["n"] += 1
        raise httpx.ConnectError("still down", request=httpx.Request("POST", "http://x"))

    monkeypatch.setattr(llm._client, "post", fake_post)

    with pytest.raises(httpx.ConnectError):
        await llm.generate(_request())

    assert calls["n"] == 3  # initial attempt + 2 retries


async def test_generate_does_not_retry_4xx(llm, monkeypatch):
    calls = {"n": 0}

    async def fake_post(path, json):
        calls["n"] += 1
        req = httpx.Request("POST", "http://x/api/chat")
        resp = httpx.Response(400, json={"error": "bad model"}, request=req)
        raise httpx.HTTPStatusError("bad request", request=req, response=resp)

    monkeypatch.setattr(llm._client, "post", fake_post)

    with pytest.raises(httpx.HTTPStatusError):
        await llm.generate(_request())

    assert calls["n"] == 1  # no retries on a 4xx


async def test_generate_retries_5xx(llm, monkeypatch):
    calls = {"n": 0}

    async def fake_post(path, json):
        calls["n"] += 1
        if calls["n"] == 1:
            req = httpx.Request("POST", "http://x/api/chat")
            resp = httpx.Response(503, json={"error": "loading model"}, request=req)
            raise httpx.HTTPStatusError("unavailable", request=req, response=resp)
        return _ok_response("ok after 503")

    monkeypatch.setattr(llm._client, "post", fake_post)

    result = await llm.generate(_request())
    assert result.content == "ok after 503"
    assert calls["n"] == 2


class _FakeStreamResp:
    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class _FakeStreamCtx:
    def __init__(self, outcome):
        self._outcome = outcome

    async def __aenter__(self):
        if isinstance(self._outcome, Exception):
            raise self._outcome
        return self._outcome

    async def __aexit__(self, *args):
        return False


async def test_stream_retries_before_first_token_then_succeeds(llm, monkeypatch):
    calls = {"n": 0}

    def fake_stream(method, path, json):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeStreamCtx(httpx.ConnectError("down", request=httpx.Request("POST", "http://x")))
        lines = [
            '{"message": {"content": "hel"}, "done": false}',
            '{"message": {"content": "lo"}, "done": true}',
        ]
        return _FakeStreamCtx(_FakeStreamResp(lines))

    monkeypatch.setattr(llm._client, "stream", fake_stream)

    tokens = [tok async for tok in llm.stream(_request())]

    assert "".join(tokens) == "hello"
    assert calls["n"] == 2
