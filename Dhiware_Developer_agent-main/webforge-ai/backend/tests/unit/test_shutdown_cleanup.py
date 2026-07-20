"""Regression tests for audit item 4.4: shutdown must close the shared
httpx client and terminate any still-running preview dev servers instead of
leaving them orphaned.
"""
import app.main as main_module
from app.orchestrator.orchestrator import orchestrator


async def test_lifespan_shutdown_closes_llm_client_and_stops_previews(monkeypatch):
    async def fake_init_db():
        return None

    closed = {"called": False}
    stopped = {"called": False}

    async def fake_close():
        closed["called"] = True

    async def fake_stop_all():
        stopped["called"] = True

    monkeypatch.setattr(main_module, "init_db", fake_init_db)
    monkeypatch.setattr(main_module.llm_service, "close", fake_close)
    monkeypatch.setattr(orchestrator.preview, "stop_all", fake_stop_all)

    async with main_module.lifespan(main_module.app):
        pass

    assert closed["called"] is True
    assert stopped["called"] is True


async def test_preview_agent_stop_all_terminates_every_tracked_process():
    from app.agents.preview_agent import PreviewAgent
    from app.core.llm_service import LLMService

    agent = PreviewAgent(LLMService())

    class FakeProcess:
        def __init__(self):
            self.terminated = False
            self.killed = False

        def terminate(self):
            self.terminated = True

        def poll(self):
            return 0  # already exited after terminate()

        def kill(self):
            self.killed = True

    p1, p2 = FakeProcess(), FakeProcess()
    agent._processes["proj-1"] = p1
    agent._processes["proj-2"] = p2

    await agent.stop_all()

    assert p1.terminated is True
    assert p2.terminated is True
    assert agent._processes == {}
