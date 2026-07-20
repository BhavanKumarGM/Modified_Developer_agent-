"""Regression test for audit item 3.3: refactor/rename search must find
every file that imports the renamed symbol, including under a different
local alias — not just files matched by keyword/filename heuristics.
"""
import pytest

from app.agents.base_agent import AgentContext
from app.agents.search_agent import SearchAgent


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
    # Imported under a DIFFERENT local name — a keyword search for "Button"
    # would miss this file's usage entirely.
    (root / "src" / "pages" / "Settings.tsx").write_text(
        "import { Button as PrimaryAction } from '../components/Button'\n"
        "export default function Settings() { return <PrimaryAction /> }\n",
        encoding="utf-8",
    )
    (root / "src" / "pages" / "Unrelated.tsx").write_text(
        "export default function Unrelated() { return <div>hi</div> }\n",
        encoding="utf-8",
    )
    return root


async def test_finds_direct_and_aliased_importers(fixture_project):
    agent = SearchAgent(llm=object())
    files = await agent._find_files_importing_symbols(["Button"], fixture_project)

    assert "src/pages/Home.tsx" in files
    assert "src/pages/Settings.tsx" in files  # aliased import — must not be missed
    assert "src/pages/Unrelated.tsx" not in files


async def test_run_merges_import_graph_results_via_symbols_kwarg(fixture_project):
    agent = SearchAgent(llm=object())
    context = AgentContext(project_id="p1", project_name="Test", root_path=str(fixture_project))

    result = await agent.run(
        "rename Button to PrimaryButton", context, symbols=["Button", "PrimaryButton"]
    )

    files = result.data["files"]
    assert "src/pages/Home.tsx" in files
    assert "src/pages/Settings.tsx" in files
