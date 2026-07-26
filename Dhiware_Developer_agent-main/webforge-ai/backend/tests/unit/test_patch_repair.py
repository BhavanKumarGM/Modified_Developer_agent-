"""Regression tests for audit item: search/replace patches that fail an
exact match must not be a dead end. Reproduces the live bug: repeated
"Could not apply patch to `TopNavigation.tsx`" with no recovery, because
the only fallback file_service.flexible_find can't help with (a genuinely
different search text, not just whitespace) had no repair path either.
"""
import pytest

from app.agents.base_agent import AgentContext, AgentResult
from app.orchestrator.orchestrator import Orchestrator


@pytest.fixture()
def orch():
    return Orchestrator()


async def test_whitespace_mismatched_patch_is_applied_via_flexible_find(orch, tmp_path, monkeypatch):
    """The fast, deterministic path: no LLM repair call needed at all."""
    root = tmp_path / "proj"
    (root / "src" / "components").mkdir(parents=True)
    target = root / "src" / "components" / "TopNavigation.tsx"
    target.write_text(
        "const TopNavigation = () => {\n"
        "  return (\n"
        "    <button>\n"
        "      Notifications\n"
        "    </button>\n"
        "  );\n"
        "};\n",
        encoding="utf-8",
    )

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": ["src/components/TopNavigation.tsx"]})

    async def fake_editing_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={
                "edits": [
                    {
                        "path": "src/components/TopNavigation.tsx",
                        # Different indentation than the real file — a
                        # plain exact match fails, flexible_find must not.
                        "search": "<button>\n  Notifications\n  </button>",
                        "replacement": "<button onClick={openMenu}>\n      Notifications\n    </button>",
                    }
                ],
                "description": "made notifications clickable",
            },
        )

    editing_calls = {"n": 0}

    async def counting_editing_run(task, context, **kwargs):
        editing_calls["n"] += 1
        return await fake_editing_run(task, context, **kwargs)

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", counting_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="make the notifications icon work", message_id="m1",
    ):
        tokens.append(tok)

    result = target.read_text(encoding="utf-8")
    assert "onClick={openMenu}" in result
    assert "const TopNavigation = () => {" in result  # untouched lines survive
    assert editing_calls["n"] == 1  # resolved by flexible_find, no repair call needed
    assert not any("could not apply patch" in t.lower() for t in tokens)


async def test_genuinely_stale_patch_triggers_one_llm_repair_round(orch, tmp_path, monkeypatch):
    """When even flexible_find can't resolve it (the search text is based
    on stale/wrong content, not just different whitespace), one bounded
    repair call must be attempted before giving up."""
    root = tmp_path / "proj"
    (root / "src" / "components").mkdir(parents=True)
    target = root / "src" / "components" / "TopNavigation.tsx"
    target.write_text(
        "const TopNavigation = () => {\n"
        "  return <button>Notifications</button>;\n"
        "};\n",
        encoding="utf-8",
    )

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": ["src/components/TopNavigation.tsx"]})

    call_count = {"n": 0}

    async def fake_editing_run(task, context, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Search text bears no resemblance to the real file at all —
            # flexible_find's whitespace normalization can't save this.
            return AgentResult(
                success=True,
                data={
                    "edits": [
                        {
                            "path": "src/components/TopNavigation.tsx",
                            "search": "function TopNavigation() { return <div>old stale content</div> }",
                            "replacement": "function TopNavigation() { return <div onClick={openMenu}>new</div> }",
                        }
                    ],
                    "description": "attempt 1",
                },
            )
        # The repair round: given fresh content, produce a search that
        # actually matches.
        assert "src/components/TopNavigation.tsx" in kwargs.get("file_contents", {})
        assert "Notifications" in kwargs["file_contents"]["src/components/TopNavigation.tsx"]
        return AgentResult(
            success=True,
            data={
                "edits": [
                    {
                        "path": "src/components/TopNavigation.tsx",
                        "search": "<button>Notifications</button>",
                        "replacement": "<button onClick={openMenu}>Notifications</button>",
                    }
                ],
                "description": "repaired",
            },
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", fake_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="make the notifications icon work", message_id="m1",
    ):
        tokens.append(tok)

    result = target.read_text(encoding="utf-8")
    assert "onClick={openMenu}" in result
    assert call_count["n"] == 2  # original attempt + exactly one repair round
    joined = "".join(tokens)
    assert "could not apply patch" not in joined.lower()


async def test_repair_gives_up_gracefully_if_still_unresolved(orch, tmp_path, monkeypatch):
    """Bounded to one repair round — if the retry ALSO doesn't match, the
    original error is surfaced, not an infinite loop."""
    root = tmp_path / "proj"
    (root / "src").mkdir(parents=True)
    target = root / "src" / "Foo.tsx"
    target.write_text("export default function Foo() { return null }\n", encoding="utf-8")

    async def fake_planner_run(task, context, **kwargs):
        return AgentResult(success=True, data={"intent": "edit", "tasks": [], "requires_full_generation": False})

    async def fake_search_run(task, context, **kwargs):
        return AgentResult(success=True, data={"files": ["src/Foo.tsx"]})

    async def always_wrong_editing_run(task, context, **kwargs):
        return AgentResult(
            success=True,
            data={"edits": [{"path": "src/Foo.tsx", "search": "nonexistent text", "replacement": "x"}]},
        )

    async def fake_review_run(task, context, **kwargs):
        return AgentResult(success=True, data={"approved": True, "score": 9, "issues": []})

    monkeypatch.setattr(orch.planner, "run", fake_planner_run)
    monkeypatch.setattr(orch.search, "run", fake_search_run)
    monkeypatch.setattr(orch.editing, "run", always_wrong_editing_run)
    monkeypatch.setattr(orch.review, "run", fake_review_run)

    tokens = []
    async for tok in orch.handle_message(
        project_id="p1", project_name="Test", framework="react",
        root_path=str(root), metadata={}, conversation_history=[],
        user_message="change something", message_id="m1",
    ):
        tokens.append(tok)

    assert target.read_text(encoding="utf-8") == "export default function Foo() { return null }\n"
    assert any("could not apply patch" in t.lower() for t in tokens)
