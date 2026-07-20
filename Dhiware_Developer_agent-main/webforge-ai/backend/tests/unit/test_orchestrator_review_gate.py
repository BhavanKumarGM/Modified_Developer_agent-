"""Regression test for audit item 2.2: ReviewAgent must actually gate
writes. Before the fix, ReviewAgent was fully built but never called from
the generation/editing pipeline — files were written unconditionally.
"""
import pytest

from app.agents.base_agent import AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def _empty_stream(*args, **kwargs):
    if False:
        yield ""  # pragma: no cover — makes this an async generator


async def test_rejected_review_blocks_generation_write(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"intent": "build", "tasks": [], "requires_full_generation": True},
        )

    async def fake_codegen_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [{"path": "src/App.tsx", "content": "export default function App(){return null}"}]},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(
            success=False,
            data={
                "approved": False,
                "score": 2,
                "issues": [{"severity": "error", "file": "src/App.tsx", "message": "uses eval()"}],
            },
        )

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.codegen, "stream", _empty_stream)
    monkeypatch.setattr(orch.codegen, "run", fake_codegen_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="build me a page",
        message_id="m1",
    ):
        tokens.append(tok)

    assert not (root / "src" / "App.tsx").exists()
    joined = "".join(tokens).lower()
    assert "not** written" in joined or "not written" in joined or "flagged" in joined


async def test_approved_review_allows_write(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"intent": "build", "tasks": [], "requires_full_generation": True},
        )

    async def fake_codegen_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [{"path": "src/App.tsx", "content": "export default function App(){return null}"}]},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    async def fake_git_run(task, context, **kwargs):
        return AgentResult(success=True, content="snapshot ok")

    async def fake_memory_run(task, context, **kwargs):
        return AgentResult(success=True, data=context.metadata)

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.codegen, "stream", _empty_stream)
    monkeypatch.setattr(orch.codegen, "run", fake_codegen_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    monkeypatch.setattr(orch.git, "run", fake_git_run)
    monkeypatch.setattr(orch.memory, "run", fake_memory_run)

    async for _ in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="build me a page",
        message_id="m1",
    ):
        pass

    assert (root / "src" / "App.tsx").exists()
