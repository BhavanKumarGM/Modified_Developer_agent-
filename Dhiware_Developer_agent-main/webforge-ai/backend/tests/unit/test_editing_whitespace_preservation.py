"""Regression test for audit item 3.1: a small edit must not rewrite the
whole file. Before the fix, EditingAgent always emitted (and the
orchestrator always applied) a full-file "content" rewrite even for a
one-line change, which reformats whitespace the LLM didn't intend to touch.
"""
import pytest

from app.agents.base_agent import AgentContext, AgentResult
from app.orchestrator.orchestrator import Orchestrator

FIXTURE_CONTENT = (
    "import React from 'react'\n"
    "\n"
    "export default function App() {\n"
    "  return (\n"
    "    <div className=\"app\">\n"
    "      <h1>Hello World</h1>\n"
    "    </div>\n"
    "  )\n"
    "}\n"
)


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_one_line_change_preserves_rest_of_file_byte_for_byte(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    fixture_path = root / "src" / "App.tsx"
    fixture_path.write_text(FIXTURE_CONTENT, encoding="utf-8", newline="")

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"intent": "edit", "tasks": [], "requires_full_generation": False},
        )

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": ["src/App.tsx"]})

    # Simulate an LLM that (as real ones often do) rewrote the ENTIRE file
    # just to change one line's text — the orchestrator must still only
    # touch that line on disk.
    new_full_content = FIXTURE_CONTENT.replace("Hello World", "Hello Universe")

    async def fake_editing_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={
                "files": [{"path": "src/App.tsx", "content": new_full_content}],
                "new_files": [],
                "description": "Changed greeting text",
            },
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    async def noop_memory(task, context, files):
        return None

    monkeypatch.setattr(orch, "_update_memory", noop_memory)

    async for _ in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(root),
        metadata={},
        conversation_history=[],
        user_message="change the greeting to Hello Universe",
        message_id="m1",
    ):
        pass

    result = fixture_path.read_text(encoding="utf-8")
    assert result == new_full_content  # content is correct...
    # ...and every line except the one that changed is byte-identical.
    original_lines = FIXTURE_CONTENT.splitlines()
    result_lines = result.splitlines()
    assert len(original_lines) == len(result_lines)
    diff_lines = [i for i, (a, b) in enumerate(zip(original_lines, result_lines)) if a != b]
    assert diff_lines == [5]  # only the "<h1>Hello World</h1>" line changed
    for i in range(len(original_lines)):
        if i != 5:
            assert result_lines[i] == original_lines[i]
