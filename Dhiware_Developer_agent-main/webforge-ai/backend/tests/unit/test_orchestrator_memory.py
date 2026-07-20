"""Regression tests for audit item 2.3: MemoryAgent must actually run and
persist to ProjectModel.metadata_json, and that memory must show up in the
*next* turn's codegen/editing prompt.
"""
import uuid

import pytest
from sqlalchemy import select

import app.database.database as db_module
from app.agents.base_agent import AgentContext, AgentResult
from app.agents.code_generation_agent import CodeGenerationAgent
from app.core.llm_service import LLMRequest, LLMResponse
from app.database.models import ProjectModel
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_memory_agent_result_persists_to_project_metadata(orch, test_engine, monkeypatch):
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    test_session_local = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    # Orchestrator._update_memory does a deferred `from app.database.database
    # import AsyncSessionLocal` at call time — patching the module attribute
    # redirects it to our per-test engine without touching the real DB.
    monkeypatch.setattr(db_module, "AsyncSessionLocal", test_session_local)

    project_id = str(uuid.uuid4())
    async with test_session_local() as session:
        session.add(ProjectModel(id=project_id, name="Test", root_path="/tmp/x"))
        await session.commit()

    async def fake_memory_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"theme": "dark", "naming_convention": "camelCase", "preferred_libraries": ["zustand"]},
        )

    monkeypatch.setattr(orch.memory, "run", fake_memory_run)

    context = AgentContext(project_id=project_id, project_name="Test", root_path="/tmp/x")
    await orch._update_memory(context, "build a dashboard", [{"path": "src/App.tsx", "content": "x"}])

    async with test_session_local() as session:
        result = await session.execute(select(ProjectModel).where(ProjectModel.id == project_id))
        project = result.scalar_one()
        assert project.metadata_json
        assert project.metadata_dict["theme"] == "dark"
        assert project.metadata_dict["preferred_libraries"] == ["zustand"]


async def test_second_turn_prompt_includes_stored_memory():
    """Directly exercises CodeGenerationAgent's prompt building — the part
    of 2.3 that makes memory actually change model behavior, not just sit
    unread in the database."""
    captured: list[LLMRequest] = []

    class FakeLLM:
        async def generate(self, request: LLMRequest) -> LLMResponse:
            captured.append(request)
            return LLMResponse(content='{"files": [], "framework": "react"}', model="fake")

    agent = CodeGenerationAgent(FakeLLM())
    context = AgentContext(
        project_id="p1",
        project_name="Test",
        root_path="/tmp/x",
        metadata={
            "theme": "dark",
            "naming_convention": "camelCase",
            "preferred_libraries": ["zustand"],
        },
    )

    await agent.run("add a settings page", context, plan={})

    assert captured, "expected the agent to call llm.generate"
    prompt_text = "\n".join(m.content for m in captured[0].messages) + (captured[0].system or "")
    assert "zustand" in prompt_text
    assert "camelCase" in prompt_text
