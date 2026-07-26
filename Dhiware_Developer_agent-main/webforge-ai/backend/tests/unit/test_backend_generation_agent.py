"""BackendGenerationAgent must produce a runnable Flask app: parse the
model's JSON, and guarantee app.py + requirements.txt exist even if the
model forgets one, since PreviewAgent needs both to actually run it."""
from __future__ import annotations

import json

import pytest

from app.agents.backend_generation_agent import BackendGenerationAgent
from app.agents.base_agent import AgentContext
from app.core.llm_service import LLMResponse


class FakeLLM:
    def __init__(self, content: str):
        self._content = content

    async def generate(self, request):
        return LLMResponse(content=self._content, model="fake-model")


def _context() -> AgentContext:
    return AgentContext(project_id="p1", project_name="Test", root_path="/tmp/proj")


@pytest.mark.asyncio
async def test_run_parses_generated_files():
    payload = {
        "files": [
            {"path": "app.py", "content": "from flask import Flask\napp = Flask(__name__)\n"},
            {"path": "requirements.txt", "content": "flask>=3.0\n"},
        ],
        "framework": "flask",
        "description": "A simple API",
    }
    agent = BackendGenerationAgent(llm=FakeLLM(json.dumps(payload)))
    result = await agent.run("build a simple API", _context())

    assert result.success is True
    paths = {f["path"] for f in result.data["files"]}
    assert paths == {"app.py", "requirements.txt"}


@pytest.mark.asyncio
async def test_run_adds_missing_app_py_and_requirements():
    payload = {"files": [{"path": "models.py", "content": "class User: pass\n"}], "framework": "flask"}
    agent = BackendGenerationAgent(llm=FakeLLM(json.dumps(payload)))
    result = await agent.run("build something", _context())

    assert result.success is True
    paths = {f["path"] for f in result.data["files"]}
    assert "app.py" in paths
    assert "requirements.txt" in paths
    app_file = next(f for f in result.data["files"] if f["path"] == "app.py")
    assert "Flask(__name__)" in app_file["content"]


@pytest.mark.asyncio
async def test_run_handles_unparseable_json():
    agent = BackendGenerationAgent(llm=FakeLLM("not json at all"))
    result = await agent.run("build something", _context())
    assert result.success is False
    assert result.error


# ── db.create_all() app-context safety net ─────────────────────────────────
# Reproduces a real bug found via live testing: a model-generated Flask +
# flask-sqlalchemy app calling `db.create_all()` at module level crashes at
# import time with "Working outside of application context." — the process
# never gets far enough to bind the port, and PreviewAgent reports a bare
# timeout instead of the real cause.

@pytest.mark.asyncio
async def test_run_wraps_module_level_create_all_in_app_context():
    payload = {
        "files": [
            {"path": "app.py", "content": (
                "from flask import Flask\n"
                "from flask_sqlalchemy import SQLAlchemy\n\n"
                "app = Flask(__name__)\n"
                "db = SQLAlchemy(app)\n\n"
                "db.create_all()\n\n"
                "@app.route('/')\n"
                "def index():\n"
                "    return 'ok'\n"
            )},
            {"path": "requirements.txt", "content": "flask>=3.0\nflask-sqlalchemy>=3.0\n"},
        ],
        "framework": "flask",
    }
    agent = BackendGenerationAgent(llm=FakeLLM(json.dumps(payload)))
    result = await agent.run("build a todo API with sqlalchemy", _context())

    app_file = next(f for f in result.data["files"] if f["path"] == "app.py")
    lines = app_file["content"].splitlines()
    assert "db.create_all()" not in lines  # no unindented (module-level) call remains
    assert "with app.app_context():\n    db.create_all()" in app_file["content"]


@pytest.mark.asyncio
async def test_run_leaves_already_wrapped_create_all_untouched():
    original = (
        "from flask import Flask\n"
        "from flask_sqlalchemy import SQLAlchemy\n\n"
        "app = Flask(__name__)\n"
        "db = SQLAlchemy(app)\n\n"
        "with app.app_context():\n"
        "    db.create_all()\n"
    )
    payload = {"files": [{"path": "app.py", "content": original}], "framework": "flask"}
    agent = BackendGenerationAgent(llm=FakeLLM(json.dumps(payload)))
    result = await agent.run("build something", _context())

    app_file = next(f for f in result.data["files"] if f["path"] == "app.py")
    assert app_file["content"] == original
