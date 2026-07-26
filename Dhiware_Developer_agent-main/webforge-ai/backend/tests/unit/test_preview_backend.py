"""PreviewAgent's Python-backend execution path: command construction must
launch each framework through its own dev-server CLI (not `python file.py`)
so the port we picked is actually honored regardless of what the source
file's own app.run()/main block hardcodes, and _start must dispatch to
backend-only / frontend-only / full-stack correctly without ever spawning
a real process."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.agents.base_agent import AgentContext, AgentResult
from app.agents.preview_agent import PreviewAgent, _find_imported_pip_packages
from app.services.backend_detect import BackendInfo


@pytest.fixture
def agent():
    return PreviewAgent(llm=None)


# ── _looks_like_python_only_project ─────────────────────────────────────────

def test_python_only_true_for_bare_flask_project(agent, tmp_path: Path):
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    assert agent._looks_like_python_only_project(tmp_path) is True


def test_python_only_false_when_package_json_present(agent, tmp_path: Path):
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    assert agent._looks_like_python_only_project(tmp_path) is False


def test_python_only_false_when_src_has_tsx(agent, tmp_path: Path):
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export default function App() { return null }", encoding="utf-8")
    assert agent._looks_like_python_only_project(tmp_path) is False


# ── _build_backend_run_command ──────────────────────────────────────────────

def test_flask_run_command_uses_flask_app_env_var(agent, tmp_path: Path):
    info = BackendInfo(framework="flask", entry_file="app.py", app_module="app", app_var="app")
    venv_python = Path("/venv/python")
    cmd, env = agent._build_backend_run_command(venv_python, info, 5055)
    assert cmd == [str(venv_python), "-m", "flask", "run", "--host", "127.0.0.1", "--port", "5055"]
    assert env["FLASK_APP"] == "app"


def test_flask_run_command_with_nonstandard_app_var(agent, tmp_path: Path):
    info = BackendInfo(framework="flask", entry_file="server.py", app_module="server", app_var="my_app")
    cmd, env = agent._build_backend_run_command(Path("/venv/python"), info, 5000)
    assert env["FLASK_APP"] == "server:my_app"


def test_django_run_command_uses_manage_py_runserver(agent):
    info = BackendInfo(framework="django", entry_file="manage.py", app_module="manage")
    cmd, _ = agent._build_backend_run_command(Path("/venv/python"), info, 8123)
    assert cmd == [str(Path("/venv/python")), "manage.py", "runserver", "127.0.0.1:8123", "--noreload"]


def test_fastapi_run_command_uses_uvicorn_target(agent):
    info = BackendInfo(framework="fastapi", entry_file="main.py", app_module="main", app_var="app")
    cmd, _ = agent._build_backend_run_command(Path("/venv/python"), info, 9001)
    assert cmd == [str(Path("/venv/python")), "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "9001"]


# ── _start dispatch logic ───────────────────────────────────────────────────

def _context(root: Path) -> AgentContext:
    return AgentContext(project_id="p1", project_name="Test", root_path=str(root))


@pytest.mark.asyncio
async def test_start_runs_backend_only_for_pure_python_project(agent, tmp_path: Path):
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")

    backend_result = AgentResult(success=True, content="ok", data={"port": 5000, "url": "http://127.0.0.1:5000", "framework": "flask"})
    with patch.object(agent, "_stop", new=AsyncMock(return_value=AgentResult(success=True))), \
         patch.object(agent, "_start_backend", new=AsyncMock(return_value=backend_result)) as start_backend, \
         patch.object(agent, "_start_frontend", new=AsyncMock()) as start_frontend:
        result = await agent._start(_context(tmp_path))

    assert result.success is True
    assert result.data["port"] == 5000
    start_backend.assert_awaited_once()
    start_frontend.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_runs_frontend_only_when_no_backend_detected(agent, tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export default function App() { return null }", encoding="utf-8")

    frontend_result = AgentResult(success=True, content="ok", data={"port": 5173, "url": "http://localhost:5173"})
    with patch.object(agent, "_stop", new=AsyncMock(return_value=AgentResult(success=True))), \
         patch.object(agent, "_start_backend", new=AsyncMock()) as start_backend, \
         patch.object(agent, "_start_frontend", new=AsyncMock(return_value=frontend_result)):
        result = await agent._start(_context(tmp_path))

    assert result.success is True
    assert result.data["port"] == 5173
    start_backend.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_runs_both_for_fullstack_project(agent, tmp_path: Path):
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    backend_result = AgentResult(success=True, content="backend ok", data={"port": 5000, "url": "http://127.0.0.1:5000", "framework": "flask"})
    frontend_result = AgentResult(success=True, content="frontend ok", data={"port": 5173, "url": "http://localhost:5173"})
    with patch.object(agent, "_stop", new=AsyncMock(return_value=AgentResult(success=True))), \
         patch.object(agent, "_start_backend", new=AsyncMock(return_value=backend_result)), \
         patch.object(agent, "_start_frontend", new=AsyncMock(return_value=frontend_result)):
        result = await agent._start(_context(tmp_path))

    assert result.success is True
    assert result.data["port"] == 5173  # primary/frontend URL
    assert result.data["backendPort"] == 5000
    assert result.data["backendFramework"] == "flask"


@pytest.mark.asyncio
async def test_start_stops_backend_if_frontend_fails_in_fullstack_project(agent, tmp_path: Path):
    (tmp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)\n", encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")

    backend_result = AgentResult(success=True, content="backend ok", data={"port": 5000, "url": "http://127.0.0.1:5000", "framework": "flask"})
    frontend_result = AgentResult(success=False, error="npm install failed")
    with patch.object(agent, "_stop", new=AsyncMock(return_value=AgentResult(success=True))), \
         patch.object(agent, "_start_backend", new=AsyncMock(return_value=backend_result)), \
         patch.object(agent, "_start_frontend", new=AsyncMock(return_value=frontend_result)), \
         patch.object(agent, "_stop_backend", new=AsyncMock()) as stop_backend:
        result = await agent._start(_context(tmp_path))

    assert result.success is False
    stop_backend.assert_awaited_once_with("p1")


# ── _find_imported_pip_packages ─────────────────────────────────────────────

def test_finds_third_party_imports_and_maps_aliases(tmp_path: Path):
    (tmp_path / "app.py").write_text(
        "from flask import Flask\n"
        "import requests\n"
        "from dotenv import load_dotenv\n"
        "import os, datetime\n",
        encoding="utf-8",
    )
    packages = _find_imported_pip_packages(tmp_path)
    assert "requests" in packages
    assert "python-dotenv" in packages  # aliased from "dotenv"
    assert "flask" in packages
    assert "os" not in packages and "datetime" not in packages  # stdlib


def test_does_not_flag_local_sibling_modules(tmp_path: Path):
    (tmp_path / "app.py").write_text("import models\nfrom routes import api\n", encoding="utf-8")
    (tmp_path / "models.py").write_text("class User: pass\n", encoding="utf-8")
    (tmp_path / "routes.py").write_text("api = None\n", encoding="utf-8")
    packages = _find_imported_pip_packages(tmp_path)
    assert "models" not in packages
    assert "routes" not in packages


def test_does_not_flag_local_package_directory(tmp_path: Path):
    pkg = tmp_path / "backend"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "app.py").write_text("import backend\nimport numpy\n", encoding="utf-8")
    packages = _find_imported_pip_packages(tmp_path)
    assert "backend" not in packages
    assert "numpy" in packages


# ── _looks_like_static_site ─────────────────────────────────────────────────
# Regression coverage for a real live bug: an uploaded plain HTML/CSS/JS
# project was silently force-migrated into the canonical React/Vite shell,
# which overwrote its real index.html and rendered a blank page (main.tsx's
# `import App from './App'` resolved case-insensitively to the project's own
# non-component app.js, so React tried to render `<undefined />`).

def test_static_site_true_for_plain_html_js_project(agent, tmp_path: Path):
    (tmp_path / "index.html").write_text(
        "<html><body><script src='app.js'></script></body></html>", encoding="utf-8"
    )
    (tmp_path / "app.js").write_text("document.addEventListener('DOMContentLoaded', () => {})", encoding="utf-8")
    assert agent._looks_like_static_site(tmp_path) is True


def test_static_site_false_when_no_index_html(agent, tmp_path: Path):
    (tmp_path / "app.js").write_text("console.log('hi')", encoding="utf-8")
    assert agent._looks_like_static_site(tmp_path) is False


def test_static_site_false_for_already_canonicalized_react_shell(agent, tmp_path: Path):
    (tmp_path / "index.html").write_text(
        '<html><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>',
        encoding="utf-8",
    )
    assert agent._looks_like_static_site(tmp_path) is False


def test_static_site_false_when_tsx_files_present(agent, tmp_path: Path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("export default function App() { return null }", encoding="utf-8")
    assert agent._looks_like_static_site(tmp_path) is False


def test_static_site_false_when_package_json_declares_react(agent, tmp_path: Path):
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}', encoding="utf-8")
    assert agent._looks_like_static_site(tmp_path) is False


@pytest.mark.asyncio
async def test_start_serves_static_site_instead_of_vite(agent, tmp_path: Path):
    (tmp_path / "index.html").write_text(
        "<html><body><script src='app.js'></script></body></html>", encoding="utf-8"
    )
    (tmp_path / "app.js").write_text("console.log('hi')", encoding="utf-8")

    static_result = AgentResult(success=True, content="ok", data={"port": 4000, "url": "http://127.0.0.1:4000"})
    with patch.object(agent, "_stop", new=AsyncMock(return_value=AgentResult(success=True))), \
         patch.object(agent, "_start_static", new=AsyncMock(return_value=static_result)) as start_static, \
         patch.object(agent, "_start_frontend", new=AsyncMock()) as start_frontend:
        result = await agent._start(_context(tmp_path))

    assert result.success is True
    assert result.data["port"] == 4000
    start_static.assert_awaited_once()
    start_frontend.assert_not_awaited()
