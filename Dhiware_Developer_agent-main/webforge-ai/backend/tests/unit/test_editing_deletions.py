"""Regression test for audit item 3.2's orchestrator wiring: a "remove this
component" edit must actually delete the file, not just empty it out or
leave it untouched.
"""
import pytest

from app.agents.base_agent import AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_editing_deletions_remove_the_file(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "src" / "components").mkdir(parents=True)
    target = root / "src" / "components" / "Obsolete.tsx"
    target.write_text("export default function Obsolete() { return null }\n", encoding="utf-8")

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": ["src/components/Obsolete.tsx"]})

    async def fake_editing_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [], "new_files": [], "deletions": ["src/components/Obsolete.tsx"], "description": "removed"},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    events = []
    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    orch.register_callback("p1", lambda t, p: events.append((t, p)))

    async for _ in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="remove the Obsolete component",
        message_id="m1",
    ):
        pass

    assert not target.exists()
    assert ("file_deleted", {"path": "src/components/Obsolete.tsx"}) in events


async def test_editing_deletions_rejects_traversal(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": []})

    async def fake_editing_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [], "new_files": [], "deletions": ["../../../evil.txt"], "description": "removed"},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="remove ../../../evil.txt",
        message_id="m1",
    ):
        tokens.append(tok)

    assert not (tmp_path / "evil.txt").exists()
    assert any("invalid path" in t.lower() for t in tokens)
