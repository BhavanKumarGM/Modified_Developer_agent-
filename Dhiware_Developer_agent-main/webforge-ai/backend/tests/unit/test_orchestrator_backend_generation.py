"""Regression coverage for the "backend" planner task: it must dispatch to
BackendGenerationAgent and write files to the project root for a bare
Python project, or under backend/ when a frontend (package.json) already
exists — so generated Flask files never collide with src/."""
import pytest

from app.agents.base_agent import AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def _run_backend_task(orch, root, monkeypatch, action="build a flask API"):
    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={
                "intent": "build",
                "summary": "build backend",
                "tasks": [{"agent": "backend", "action": action, "priority": 1}],
                "requires_full_generation": False,
            },
        )

    async def fake_backend_stream(task, context, **kwargs):
        yield "Building the backend…\n"

    async def fake_backend_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={
                "files": [
                    {"path": "app.py", "content": "from flask import Flask\napp = Flask(__name__)\n"},
                    {"path": "requirements.txt", "content": "flask>=3.0\n"},
                ],
                "framework": "flask",
            },
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 10})

    async def fake_git_run(task, context, **kwargs):
        return AgentResult(success=True)

    async def fake_memory_run(task, context, **kwargs):
        return AgentResult(success=True, data={})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.backend_codegen, "stream", fake_backend_stream)
    monkeypatch.setattr(orch.backend_codegen, "run", fake_backend_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    monkeypatch.setattr(orch.git, "run", fake_git_run)
    monkeypatch.setattr(orch.memory, "run", fake_memory_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="unknown",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message=action,
        message_id="m1",
    ):
        tokens.append(tok)
    return tokens


async def test_backend_task_writes_to_root_for_bare_python_project(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    tokens = await _run_backend_task(orch, root, monkeypatch)

    assert (root / "app.py").exists()
    assert (root / "requirements.txt").exists()
    assert not (root / "backend").exists()
    assert any("Generated" in t for t in tokens)


async def test_backend_task_namespaces_under_backend_dir_for_fullstack_project(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "package.json").write_text("{}", encoding="utf-8")

    await _run_backend_task(orch, root, monkeypatch)

    assert (root / "backend" / "app.py").exists()
    assert (root / "backend" / "requirements.txt").exists()
    assert not (root / "app.py").exists()


async def test_backend_task_respects_review_rejection(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(
            success=False,
            data={"approved": False, "score": 2, "issues": [{"severity": "error", "file": "app.py", "message": "bad"}]},
        )

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={
                "intent": "build",
                "tasks": [{"agent": "backend", "action": "build a flask API", "priority": 1}],
                "requires_full_generation": False,
            },
        )

    async def fake_backend_stream(task, context, **kwargs):
        yield ""

    async def fake_backend_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [{"path": "app.py", "content": "from flask import Flask\napp = Flask(__name__)\n"}]},
        )

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.backend_codegen, "stream", fake_backend_stream)
    monkeypatch.setattr(orch.backend_codegen, "run", fake_backend_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="unknown",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="build a flask API",
        message_id="m1",
    ):
        tokens.append(tok)

    assert not (root / "app.py").exists()
    assert any("not** been written" in t or "not been written" in t or "flagged" in t.lower() for t in tokens)
