"""Regression tests reproducing the live bug: saying "apply anyway" after
a review rejection did NOT reapply the rejected proposal — it re-ran the
whole pipeline on the literal, content-free text "apply anyway", which
correctly found nothing to do and replied "No changes were necessary."
"""
import pytest

from app.agents.base_agent import AgentContext, AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_apply_anyway_reapplies_the_rejected_generation(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "build", "tasks": [], "requires_full_generation": True})

    async def empty_stream(*a, **kw):
        if False:
            yield ""

    async def fake_codegen_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [{"path": "src/utils/notify.js", "content": "alert('hi')"}]},
        )

    review_calls = {"n": 0}

    async def fake_review_run(task, context, **kwargs):
        review_calls["n"] += 1
        return AgentResult(success=True, data={"approved": False, "score": 6, "issues": [{"message": "uses alert()"}]})

    async def fake_git_run(task, context, **kwargs):
        return AgentResult(success=True, content="ok")

    async def noop_memory(task, context, files):
        return None

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.codegen, "stream", empty_stream)
    monkeypatch.setattr(orch.codegen, "run", fake_codegen_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    monkeypatch.setattr(orch.git, "run", fake_git_run)
    monkeypatch.setattr(orch, "_update_memory", noop_memory)

    # Turn 1: rejected.
    tokens1 = []
    async for tok in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="write some example notification", message_id="m1",
    ):
        tokens1.append(tok)

    assert not (root / "src" / "utils" / "notify.js").exists()
    assert "not** written" in "".join(tokens1) or "not written" in "".join(tokens1).lower()

    # Turn 2: "apply anyway" — must NOT re-run the planner/codegen at all,
    # just write the exact files that were already proposed and rejected.
    tokens2 = []
    async for tok in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="apply anyway", message_id="m2",
    ):
        tokens2.append(tok)

    assert (root / "src" / "utils" / "notify.js").exists()
    assert (root / "src" / "utils" / "notify.js").read_text(encoding="utf-8") == "alert('hi')"
    assert review_calls["n"] == 1  # review was never re-invoked on turn 2
    assert "No changes were necessary" not in "".join(tokens2)


async def test_apply_anyway_reapplies_the_rejected_edit(orch, tmp_path, monkeypatch):
    # Uses "new_files" (not "edits") because the review gate only inspects
    # files/new_files — search/replace "edits" bypass review entirely, same
    # as the real calendar-app bug this reproduces (the rejected proposal
    # was a new file, example_notification.js).
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    target = root / "src" / "notify.js"

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": []})

    async def fake_editing_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"new_files": [{"path": "src/notify.js", "content": "alert('hi')"}], "description": "add notify"},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=False, data={"approved": False, "score": 4, "issues": [{"message": "uses alert()"}]})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    # Turn 1: rejected.
    async for _ in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="add a notification helper", message_id="m1",
    ):
        pass
    assert not target.exists()

    # Turn 2: apply anyway.
    async for _ in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="apply anyway", message_id="m2",
    ):
        pass
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "alert('hi')"


async def test_apply_anyway_with_nothing_pending_is_a_harmless_noop(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "conversation", "tasks": []})

    async def fake_conversation_stream(task, context, **kwargs):
        yield "Sure — what would you like me to apply?"

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.conversation, "stream", fake_conversation_stream)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="apply anyway", message_id="m1",
    ):
        tokens.append(tok)

    # No pending proposal for this project — falls through to the normal
    # pipeline instead of silently doing nothing.
    assert tokens == ["Sure — what would you like me to apply?"]


async def test_a_second_rejection_overwrites_the_pending_proposal(orch, tmp_path, monkeypatch):
    """apply anyway must reapply the MOST RECENT rejection, not a stale one."""
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": []})

    call_count = {"n": 0}

    async def fake_editing_run(task, context, **kwargs):
        call_count["n"] += 1
        letter = "A" if call_count["n"] == 1 else "B"
        return AgentResult(
            success=True,
            data={"new_files": [{"path": f"src/{letter}.tsx", "content": f"export default function {letter}() {{ return null }}"}]},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=False, data={"approved": False, "score": 3, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    for msg in ("create A", "create B"):
        async for _ in orch.handle_message(
            project_id="p1", project_name="Test", framework="react",
            root_path=str(root), metadata={}, conversation_history=[],
            user_message=msg, message_id=msg,
        ):
            pass

    assert not (root / "src" / "A.tsx").exists()
    assert not (root / "src" / "B.tsx").exists()

    async for _ in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="apply anyway", message_id="m3",
    ):
        pass

    # Only B (the most recent rejection) gets applied — A was superseded.
    assert (root / "src" / "B.tsx").exists()
    assert not (root / "src" / "A.tsx").exists()
