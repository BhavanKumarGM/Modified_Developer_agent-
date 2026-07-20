"""Regression tests for audit item 4.3: writes for a single project must be
serialized so two concurrent edits can't race on the same file.
"""
import asyncio

import pytest

from app.agents.base_agent import AgentContext, AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_same_project_id_returns_the_same_lock(orch):
    lock_a = orch._get_write_lock("p1")
    lock_b = orch._get_write_lock("p1")
    assert lock_a is lock_b


async def test_different_projects_get_independent_locks(orch):
    lock_p1 = orch._get_write_lock("p1")
    lock_p2 = orch._get_write_lock("p2")
    assert lock_p1 is not lock_p2


async def test_write_lock_serializes_concurrent_critical_sections(orch):
    """Two coroutines racing for the same project's write lock must never
    be inside their critical section at the same time — the actual
    mechanism _write_files/_apply_edits rely on."""
    events: list[tuple[str, str]] = []

    async def critical_section(name: str, hold_seconds: float):
        async with orch._get_write_lock("p1"):
            events.append(("start", name))
            await asyncio.sleep(hold_seconds)
            events.append(("end", name))

    # B starts slightly after A but requests a shorter hold — if the lock
    # didn't serialize them, B's "start" would land between A's start/end.
    await asyncio.gather(
        critical_section("A", 0.05),
        _delayed(critical_section("B", 0.01), 0.01),
    )

    assert events[0] == ("start", "A")
    assert events[1] == ("end", "A")
    assert events[2] == ("start", "B")
    assert events[3] == ("end", "B")


async def _delayed(coro, delay: float):
    await asyncio.sleep(delay)
    await coro


async def test_generation_write_phase_acquires_the_project_lock(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "build", "tasks": [], "requires_full_generation": True})

    async def empty_stream(*a, **kw):
        if False:
            yield ""

    async def fake_codegen_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": [{"path": "src/App.tsx", "content": "x"}]})

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    async def fake_git_run(task, context, **kwargs):
        return AgentResult(success=True, content="ok")

    lock_calls: list[str] = []
    real_get_lock = orch._get_write_lock

    def spy_get_lock(project_id):
        lock_calls.append(project_id)
        return real_get_lock(project_id)

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.codegen, "stream", empty_stream)
    monkeypatch.setattr(orch.codegen, "run", fake_codegen_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    monkeypatch.setattr(orch.git, "run", fake_git_run)
    monkeypatch.setattr(orch, "_get_write_lock", spy_get_lock)

    async def noop_memory(task, context, files):
        return None

    monkeypatch.setattr(orch, "_update_memory", noop_memory)

    async for _ in orch.handle_message(
        project_id="proj-42",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="build a page",
        message_id="m1",
    ):
        pass

    assert "proj-42" in lock_calls
