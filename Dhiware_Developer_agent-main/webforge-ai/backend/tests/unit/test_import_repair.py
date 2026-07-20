"""Regression tests reproducing a live bug report: generated/edited code
importing sibling files that were never actually created (e.g.
BillingScreen.tsx importing ./InvoiceTable with no InvoiceTable.tsx
anywhere in the project). Before the fix, this only surfaced as a wall of
tsc "Cannot find module" errors when the user tried to preview — no
recovery path.

The fix lives at the Orchestrator level (Orchestrator._repair_missing_local_imports),
operating on real on-disk content after files are written, and resolving
against the whole project tree — not a possibly-incomplete pre-fetched
snapshot. An earlier version of this lived inside EditingAgent operating on
SearchAgent's `file_contents[:8]` snapshot; that version could silently
miss the very file being edited when SearchAgent didn't happen to include
it, which is exactly the bug this test suite pins down.
"""
import pytest

from app.agents.base_agent import AgentContext, AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_repairs_missing_imports_after_generation_writes_to_disk(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "src" / "components").mkdir(parents=True)

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "build", "tasks": [], "requires_full_generation": True})

    async def empty_stream(*a, **kw):
        if False:
            yield ""

    async def fake_codegen_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={
                "files": [
                    {
                        "path": "src/components/BillingScreen.tsx",
                        "content": (
                            "import InvoiceTable from './InvoiceTable'\n"
                            "export default function BillingScreen() { return null }\n"
                        ),
                    }
                ]
            },
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    async def fake_git_run(task, context, **kwargs):
        return AgentResult(success=True, content="ok")

    async def noop_memory(task, context, files):
        return None

    repair_calls = []

    async def fake_editing_run(task, context, **kwargs):
        repair_calls.append(kwargs.get("file_contents", {}))
        return AgentResult(
            success=True,
            data={
                "new_files": [
                    {"path": "src/components/InvoiceTable.tsx", "content": "export default function InvoiceTable() { return null }\n"}
                ]
            },
        )

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.codegen, "stream", empty_stream)
    monkeypatch.setattr(orch.codegen, "run", fake_codegen_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    monkeypatch.setattr(orch.git, "run", fake_git_run)
    monkeypatch.setattr(orch, "_update_memory", noop_memory)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)

    async for _ in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="build a billing screen", message_id="m1",
    ):
        pass

    assert (root / "src" / "components" / "InvoiceTable.tsx").exists()
    # The repair call must have been given the ACTUAL importing file's
    # content (the whole point of the fix), not an empty/incomplete context.
    assert any("src/components/BillingScreen.tsx" in fc for fc in repair_calls)


async def test_repairs_missing_imports_introduced_by_an_edit_even_when_search_misses_the_file(
    orch, tmp_path, monkeypatch
):
    """Pins down the exact bug: SearchAgent's file_contents snapshot for
    this turn does NOT include the file the edit actually touches, but the
    real on-disk write still happens — repair must still catch it."""
    root = tmp_path / "proj"
    (root / "src" / "components").mkdir(parents=True)
    billing = root / "src" / "components" / "BillingScreen.tsx"
    billing.write_text("export default function BillingScreen() { return null }\n", encoding="utf-8")

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        # Deliberately returns nothing useful — simulates SearchAgent not
        # surfacing BillingScreen.tsx for this specific sub-task's query.
        return AgentResult(success=True, data={"files": []})

    call_count = {"n": 0}

    async def fake_editing_run(task, context, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First call: the "real" edit, which the model applies to a file
            # not in its given file_contents (small models don't always
            # respect "only edit files you were shown").
            return AgentResult(
                success=True,
                data={
                    "edits": [
                        {
                            "path": "src/components/BillingScreen.tsx",
                            "search": "export default function BillingScreen() { return null }",
                            "replacement": (
                                "import InvoiceTable from './InvoiceTable'\n"
                                "export default function BillingScreen() { return null }"
                            ),
                        }
                    ],
                    "description": "added import",
                },
            )
        # Second call: the orchestrator's repair round.
        return AgentResult(
            success=True,
            data={"new_files": [{"path": "src/components/InvoiceTable.tsx", "content": "export default function InvoiceTable() { return null }\n"}]},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    async for _ in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="import missing components in BillingScreen.tsx", message_id="m1",
    ):
        pass

    assert (root / "src" / "components" / "InvoiceTable.tsx").exists()
    assert call_count["n"] == 2


async def test_no_repair_call_when_nothing_is_missing(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "src" / "components").mkdir(parents=True)
    (root / "src" / "components" / "Hero.tsx").write_text(
        "export default function Hero() { return null }\n", encoding="utf-8"
    )

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "build", "tasks": [], "requires_full_generation": True})

    async def empty_stream(*a, **kw):
        if False:
            yield ""

    async def fake_codegen_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [{"path": "src/App.tsx", "content": "import Hero from './components/Hero'\n"}]},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    async def fake_git_run(task, context, **kwargs):
        return AgentResult(success=True, content="ok")

    async def noop_memory(task, context, files):
        return None

    editing_calls = []

    async def fake_editing_run(task, context, **kwargs):
        editing_calls.append(task)
        return AgentResult(success=True, data={})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.codegen, "stream", empty_stream)
    monkeypatch.setattr(orch.codegen, "run", fake_codegen_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    monkeypatch.setattr(orch.git, "run", fake_git_run)
    monkeypatch.setattr(orch, "_update_memory", noop_memory)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)

    async for _ in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="build something", message_id="m1",
    ):
        pass

    assert editing_calls == []  # no repair call needed — nothing was missing


async def test_repair_gives_up_gracefully_after_max_rounds(orch, tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "build", "tasks": [], "requires_full_generation": True})

    async def empty_stream(*a, **kw):
        if False:
            yield ""

    async def fake_codegen_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"files": [{"path": "src/App.tsx", "content": "import X from './StillMissing'\n"}]},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    async def fake_git_run(task, context, **kwargs):
        return AgentResult(success=True, content="ok")

    async def noop_memory(task, context, files):
        return None

    call_count = {"n": 0}

    async def fake_editing_run(task, context, **kwargs):
        call_count["n"] += 1
        # Always "fixes" it by generating another file that itself imports
        # something else missing — must not loop forever.
        return AgentResult(
            success=True,
            data={"new_files": [{"path": f"src/Extra{call_count['n']}.tsx", "content": "import Y from './AlsoMissing'\n"}]},
        )

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.codegen, "stream", empty_stream)
    monkeypatch.setattr(orch.codegen, "run", fake_codegen_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)
    monkeypatch.setattr(orch.git, "run", fake_git_run)
    monkeypatch.setattr(orch, "_update_memory", noop_memory)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)

    async for _ in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="build something", message_id="m1",
    ):
        pass

    assert call_count["n"] == Orchestrator.IMPORT_REPAIR_MAX_ROUNDS  # bounded, doesn't loop forever
