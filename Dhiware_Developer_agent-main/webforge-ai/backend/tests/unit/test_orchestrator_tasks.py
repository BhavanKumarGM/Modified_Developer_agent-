"""Regression test for audit item 2.1: the planner's plan["tasks"] must
actually drive execution (dispatched to the named agent, in priority
order), instead of being computed and thrown away in favor of a single
intent branch.
"""
import pytest

from app.agents.base_agent import AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_planner_tasks_dispatch_to_agents_in_priority_order(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    call_order: list[str] = []

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={
                "intent": "analyze",
                "summary": "look around then search",
                "tasks": [
                    {"agent": "search", "action": "find auth files", "priority": 2},
                    {"agent": "repository", "action": "analyze structure", "priority": 1},
                ],
                "requires_full_generation": False,
            },
        )

    async def fake_search_run(task, context, **kwargs):
        call_order.append("search")
        return AgentResult(success=True, data={"files": ["src/App.tsx"]})

    async def fake_repository_run(task, context, **kwargs):
        call_order.append("repository")
        return AgentResult(success=True, data={"summary": "a react app"})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.repository, "run", fake_repository_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="what's in this project and where's auth?",
        message_id="m1",
    ):
        tokens.append(tok)

    # priority 1 (repository) must run before priority 2 (search), regardless
    # of their order in plan["tasks"].
    assert call_order == ["repository", "search"]
    assert any("relevant file" in t.lower() for t in tokens)
    assert any("repository analysis" in t.lower() for t in tokens)


async def test_malformed_tasks_fall_back_to_single_intent_branch(orch, tmp_path, monkeypatch):
    """Ground rule: don't regress robustness — an empty/malformed tasks[]
    must fall back to today's single intent-branch behavior, not crash."""
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"intent": "conversation", "tasks": "not-a-list", "requires_full_generation": False},
        )

    async def fake_conversation_stream(task, context, **kwargs):
        yield "hello there"

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.conversation, "stream", fake_conversation_stream)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="hi",
        message_id="m1",
    ):
        tokens.append(tok)

    assert tokens == ["hello there"]
