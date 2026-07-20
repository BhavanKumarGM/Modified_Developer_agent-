"""Regression tests for audit item 6.3: every log line emitted during one
chat turn (planner -> agents -> git -> WS events) must carry that turn's
message_id, so the turn can be traced end-to-end via `grep <message_id>`.
"""
import logging

import pytest

from app.agents.base_agent import AgentResult
from app.core.logging_context import MessageIdFilter, message_id_var
from app.orchestrator.orchestrator import Orchestrator


def test_message_id_filter_attaches_the_current_correlation_id():
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    token = message_id_var.set("turn-abc-123")
    try:
        result = MessageIdFilter().filter(record)
    finally:
        message_id_var.reset(token)

    assert result is True
    assert record.message_id == "turn-abc-123"


def test_message_id_defaults_to_placeholder_outside_any_turn():
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello", args=(), exc_info=None,
    )
    MessageIdFilter().filter(record)
    assert record.message_id == "-"


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_correlation_id_is_set_for_the_whole_turn_and_reset_after(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    observed_during_planner = []
    observed_during_conversation = []

    async def fake_planner_run(task, context, **kwargs):
        observed_during_planner.append(message_id_var.get())
        return AgentResult(success=True, data={"intent": "conversation", "tasks": []})

    async def fake_conversation_stream(task, context, **kwargs):
        observed_during_conversation.append(message_id_var.get())
        yield "hi"

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.conversation, "stream", fake_conversation_stream)

    assert message_id_var.get() == "-"  # nothing in flight before the call

    async for _ in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="hello",
        message_id="turn-xyz-789",
    ):
        pass

    assert observed_during_planner == ["turn-xyz-789"]
    assert observed_during_conversation == ["turn-xyz-789"]
    # Reset once the turn is over — must not leak into whatever runs next.
    assert message_id_var.get() == "-"


async def test_different_turns_get_different_correlation_ids(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()

    seen: list[str] = []

    async def fake_planner_run(task, context, **kwargs):
        seen.append(message_id_var.get())
        return AgentResult(success=True, data={"intent": "conversation", "tasks": []})

    async def fake_conversation_stream(task, context, **kwargs):
        yield "hi"

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.conversation, "stream", fake_conversation_stream)

    for mid in ("turn-1", "turn-2"):
        async for _ in orch.handle_message(
            project_id="p1", project_name="Test", framework="react",
            root_path=str(root), metadata={}, conversation_history=[],
            user_message="hello", message_id=mid,
        ):
            pass

    assert seen == ["turn-1", "turn-2"]
