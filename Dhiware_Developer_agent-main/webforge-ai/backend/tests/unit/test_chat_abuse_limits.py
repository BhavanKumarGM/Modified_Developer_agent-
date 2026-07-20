"""Regression tests for audit item 4.5: oversized or rapid-fire /chat/send
requests must be rejected with a clear error, not silently accepted/degraded.
"""
import app.routers.chat as chat_module
from app.core.config import settings
from app.core.rate_limiter import RateLimiter


async def _noop_handle_message(**kwargs):
    return
    yield  # pragma: no cover — makes this an async generator


async def test_oversized_message_rejected_with_400(client, project, monkeypatch):
    monkeypatch.setattr(chat_module.orchestrator, "handle_message", _noop_handle_message)

    too_long = "x" * (settings.max_message_length + 1)
    resp = await client.post(
        "/api/chat/send", json={"projectId": project["id"], "message": too_long}
    )
    assert resp.status_code == 400
    assert "too long" in resp.json()["detail"].lower()


async def test_message_at_the_limit_is_accepted(client, project, monkeypatch):
    monkeypatch.setattr(chat_module.orchestrator, "handle_message", _noop_handle_message)
    # Give this test its own rate limiter so it isn't affected by others.
    monkeypatch.setattr(chat_module, "_chat_rate_limiter", RateLimiter(max_requests=100))

    exactly_at_limit = "x" * settings.max_message_length
    resp = await client.post(
        "/api/chat/send", json={"projectId": project["id"], "message": exactly_at_limit}
    )
    assert resp.status_code == 200


async def test_rapid_fire_requests_are_rate_limited(client, project, monkeypatch):
    monkeypatch.setattr(chat_module.orchestrator, "handle_message", _noop_handle_message)
    monkeypatch.setattr(chat_module, "_chat_rate_limiter", RateLimiter(max_requests=2))

    r1 = await client.post("/api/chat/send", json={"projectId": project["id"], "message": "hi"})
    r2 = await client.post("/api/chat/send", json={"projectId": project["id"], "message": "hi"})
    r3 = await client.post("/api/chat/send", json={"projectId": project["id"], "message": "hi"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r3.status_code == 429
    assert "too many requests" in r3.json()["detail"].lower()


async def test_rate_limit_is_scoped_per_project(client, project, monkeypatch):
    monkeypatch.setattr(chat_module.orchestrator, "handle_message", _noop_handle_message)
    monkeypatch.setattr(chat_module, "_chat_rate_limiter", RateLimiter(max_requests=1))

    other_resp = await client.post("/api/projects", json={"name": "Other Project"})
    other_project = other_resp.json()

    r1 = await client.post("/api/chat/send", json={"projectId": project["id"], "message": "hi"})
    r2 = await client.post("/api/chat/send", json={"projectId": other_project["id"], "message": "hi"})

    assert r1.status_code == 200
    assert r2.status_code == 200  # a different project isn't throttled by project A's usage
