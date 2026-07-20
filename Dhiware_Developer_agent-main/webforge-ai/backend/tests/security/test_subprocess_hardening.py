"""Regression tests for preview_agent.py subprocess hardening.

Before the fix, npm/npx were invoked via shell=True with an interpolated
string command — a classic shell-injection shape even though today's
callers happen to only interpolate an internally-chosen port number. The
fix uses shell=False with an argument list and a PATH-resolved executable
for every subprocess call in this module.
"""
import inspect
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents import preview_agent as preview_agent_module
from app.agents.preview_agent import PreviewAgent
from app.core.llm_service import LLMService


def test_no_shell_true_anywhere_in_preview_agent():
    source = inspect.getsource(preview_agent_module)
    assert "shell=True" not in source


def test_run_npm_install_uses_shell_false_and_arg_list(tmp_path: Path):
    agent = PreviewAgent(LLMService())

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, stdout="ok", stderr="")

    with patch.object(preview_agent_module.shutil, "which", return_value="/usr/bin/npm"), \
         patch.object(preview_agent_module.subprocess, "run", side_effect=fake_run):
        returncode, output = agent._run_npm_install(tmp_path)

    assert returncode == 0
    assert isinstance(captured["args"], list)
    assert captured["args"][0] == "/usr/bin/npm"
    assert all(isinstance(a, str) for a in captured["args"])
    assert captured["kwargs"]["shell"] is False


def test_run_typecheck_uses_shell_false_and_arg_list(tmp_path: Path):
    agent = PreviewAgent(LLMService())

    captured = {}

    def fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    with patch.object(preview_agent_module.shutil, "which", return_value="/usr/bin/npx"), \
         patch.object(preview_agent_module.subprocess, "run", side_effect=fake_run):
        ok, output = agent._run_typecheck(tmp_path)

    assert ok is True
    assert isinstance(captured["args"], list)
    assert captured["args"][0] == "/usr/bin/npx"
    assert all(isinstance(a, str) for a in captured["args"])
    assert captured["kwargs"]["shell"] is False


def test_missing_executable_raises_clear_error(tmp_path: Path):
    agent = PreviewAgent(LLMService())
    with patch.object(preview_agent_module.shutil, "which", return_value=None):
        with pytest.raises(FileNotFoundError):
            agent._run_npm_install(tmp_path)


def test_dev_server_popen_uses_shell_false_and_arg_list(tmp_path: Path, monkeypatch):
    """Covers the third subprocess call site (starting the Vite dev server)
    without needing a real npm/Vite: we run `_start` and intercept Popen."""
    import asyncio

    agent = PreviewAgent(LLMService())

    (tmp_path / "src").mkdir()
    captured = {}

    class FakeProcess:
        def poll(self):
            return None

        stdout = None

        def terminate(self):
            pass

        def kill(self):
            pass

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProcess()

    async def fake_wait_for_port(port, timeout, process):
        return True

    monkeypatch.setattr(preview_agent_module.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(preview_agent_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(agent, "_needs_npm_install", lambda root: False)
    monkeypatch.setattr(agent, "_run_typecheck", lambda root: (True, ""))
    monkeypatch.setattr(agent, "_wait_for_port", fake_wait_for_port)
    monkeypatch.setattr(agent, "_find_port", lambda: asyncio.sleep(0, result=3100))

    from app.agents.base_agent import AgentContext

    context = AgentContext(project_id="p1", project_name="Test", root_path=str(tmp_path))
    result = asyncio.run(agent._start(context))

    assert result.success is True
    assert isinstance(captured["args"], list)
    assert all(isinstance(a, str) for a in captured["args"])
    assert captured["kwargs"]["shell"] is False
    assert captured["args"][0] == "/usr/bin/npm"
