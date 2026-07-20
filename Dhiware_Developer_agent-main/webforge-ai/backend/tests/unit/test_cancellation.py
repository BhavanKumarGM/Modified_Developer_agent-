"""Regression tests for audit item 4.2: a WebSocket "stop" message must
actually cancel the in-flight generation/edit, not just be ignored.
"""
import asyncio

import pytest

from app.agents.base_agent import AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_cancel_active_task_cancels_in_flight_generation(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    started = asyncio.Event()

    async def slow_planner_run(task, context, **kwargs):
        started.set()
        await asyncio.sleep(10)  # stands in for a slow/hanging Ollama call
        return AgentResult(success=True, data={"intent": "conversation", "tasks": []})

    monkeypatch.setattr(orch.planner, "run", slow_planner_run)

    async def run_pipeline():
        async for _ in orch.handle_message(
            project_id="p1",
            project_name="Test",
            framework="react",
            root_path=str(root),
            metadata={},
            conversation_history=[],
            user_message="build something big",
            message_id="m1",
        ):
            pass

    task = asyncio.create_task(run_pipeline())
    orch.register_task("p1", task)

    await asyncio.wait_for(started.wait(), timeout=2)

    cancelled = orch.cancel_active_task("p1")
    assert cancelled is True

    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


async def test_cancel_active_task_returns_false_when_nothing_running(orch):
    assert orch.cancel_active_task("no-such-project") is False


async def test_unregister_task_only_clears_the_matching_task(orch):
    async def noop():
        pass

    task_a = asyncio.create_task(noop())
    task_b = asyncio.create_task(noop())
    await task_a
    await task_b

    orch.register_task("p1", task_a)
    # A stale reference to an old task must not clobber a newer one.
    orch.register_task("p1", task_b)
    orch.unregister_task("p1", task_a)

    assert orch._active_tasks.get("p1") is task_b


async def test_websocket_stop_message_triggers_cancel(monkeypatch):
    """End-to-end-ish check of main.py's WS handler wiring, without needing
    a real WebSocket: verifies the "stop" message type is routed to
    orchestrator.cancel_active_task for the connecting project_id."""
    import json as _json

    from app.orchestrator.orchestrator import orchestrator as global_orchestrator

    calls = []
    monkeypatch.setattr(global_orchestrator, "cancel_active_task", lambda pid: calls.append(pid) or True)

    class FakeWebSocket:
        def __init__(self, incoming):
            self._incoming = list(incoming)
            self.sent = []

        async def accept(self):
            pass

        async def receive_text(self):
            if not self._incoming:
                from fastapi import WebSocketDisconnect

                raise WebSocketDisconnect()
            return self._incoming.pop(0)

        async def send_text(self, data):
            self.sent.append(data)

    import app.main as main_module

    ws = FakeWebSocket([_json.dumps({"type": "stop"})])
    await main_module.websocket_endpoint(ws, "proj-xyz")

    assert calls == ["proj-xyz"]
    assert any('"stop_ack"' in s for s in ws.sent)
