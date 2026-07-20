"""End-to-end regression test for audit item 3.3: a rename request routed
through the orchestrator must produce edits touching every file that
imports the renamed symbol, including via a different local alias — not
just the files a keyword search would have found.
"""
import pytest

from app.agents.base_agent import AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


@pytest.fixture()
def fixture_project(tmp_path):
    root = tmp_path / "proj"
    (root / "src" / "components").mkdir(parents=True)
    (root / "src" / "pages").mkdir(parents=True)

    (root / "src" / "components" / "Button.tsx").write_text(
        "export function Button() { return null }\n", encoding="utf-8"
    )
    (root / "src" / "pages" / "Home.tsx").write_text(
        "import { Button } from '../components/Button'\n"
        "export default function Home() { return <Button /> }\n",
        encoding="utf-8",
    )
    (root / "src" / "pages" / "Settings.tsx").write_text(
        "import { Button as PrimaryAction } from '../components/Button'\n"
        "export default function Settings() { return <PrimaryAction /> }\n",
        encoding="utf-8",
    )
    return root


async def test_rename_request_produces_edits_touching_all_importing_files(
    orch, fixture_project, monkeypatch
):
    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"intent": "refactor", "tasks": [], "requires_full_generation": False},
        )

    seen_file_contents: dict = {}

    async def fake_editing_run(task, context, **kwargs):
        file_contents = kwargs.get("file_contents", {})
        seen_file_contents.update(file_contents)
        # Emit a no-op edit for every file we were shown, so the applied
        # changes report reflects exactly which files reached the agent.
        edits = [
            {"path": path, "search": "Button", "replacement": "PrimaryButton"}
            for path in file_contents
            if "Button" in file_contents[path]
        ]
        return AgentResult(success=True, data={"edits": edits, "description": "renamed"})

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    async for _ in orch.handle_message(
        project_id="p1",
        project_name="Test",
        framework="react",
        root_path=str(fixture_project),
        metadata={},
        conversation_history=[],
        user_message="rename Button to PrimaryButton",
        message_id="m1",
    ):
        pass

    # Both the directly-imported and the aliased-imported file must have
    # been read and handed to the editing agent.
    assert "src/pages/Home.tsx" in seen_file_contents
    assert "src/pages/Settings.tsx" in seen_file_contents

    # And both files' content on disk actually changed.
    home_content = (fixture_project / "src" / "pages" / "Home.tsx").read_text(encoding="utf-8")
    settings_content = (fixture_project / "src" / "pages" / "Settings.tsx").read_text(encoding="utf-8")
    assert "PrimaryButton" in home_content
    assert "PrimaryButton" in settings_content
