"""Unit tests for app.services.search_index.SearchIndex — the sqlite-vec
backed local semantic index (audit items 5.1 and 5.2).

Real embedding inference can't run in a unit test (no Ollama here), so
`embed_fn` is mocked with a deterministic function that maps specific
marker substrings to specific vector directions — this still exercises the
real chunking/storage/KNN-search code path, just with "understanding
semantic similarity" stubbed out.
"""
import pytest

from app.services.search_index import SearchIndex


async def _fake_embed(text: str) -> list[float]:
    if "grandTotalWithTax" in text or "checkout basket total" in text.lower():
        return [1.0, 0.0, 0.0]
    return [0.0, 1.0, 0.0]


@pytest.fixture()
def fixture_project(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "projects_dir", tmp_path / "projects")

    root = tmp_path / "proj"
    (root / "src" / "utils").mkdir(parents=True)
    (root / "src" / "components").mkdir(parents=True)

    (root / "src" / "utils" / "pricing.ts").write_text(
        "export function grandTotalWithTax(items) { return items.reduce((a, b) => a + b.price, 0) * 1.08 }\n",
        encoding="utf-8",
    )
    (root / "src" / "components" / "Footer.tsx").write_text(
        "export function Footer() { return <footer>copyright</footer> }\n",
        encoding="utf-8",
    )
    return root


async def test_semantically_phrased_query_finds_the_right_file(fixture_project):
    index = SearchIndex("proj-sem-1", embedding_dim=3)
    await index.sync(fixture_project, _fake_embed)

    results = await index.search("what computes the checkout basket total", _fake_embed, top_k=5)

    # The query shares no literal keywords with "grandTotalWithTax" — only
    # the (mocked) embedding similarity ties them together. It must rank
    # first, ahead of the unrelated Footer component.
    assert results[0] == "src/utils/pricing.ts"


async def test_semantic_search_ranks_the_relevant_file_above_unrelated_ones(fixture_project):
    index = SearchIndex("proj-sem-1b", embedding_dim=3)
    await index.sync(fixture_project, _fake_embed)

    results = await index.search("what computes the checkout basket total", _fake_embed, top_k=1)

    assert results == ["src/utils/pricing.ts"]


async def test_second_sync_on_unchanged_project_reads_no_files(fixture_project):
    index = SearchIndex("proj-sem-2", embedding_dim=3)
    seen: list[str] = []
    await index.sync(fixture_project, _fake_embed, _read_files_seen=seen)
    assert len(seen) == 2  # both fixture files read on first sync

    seen2: list[str] = []
    await index.sync(fixture_project, _fake_embed, _read_files_seen=seen2)
    assert seen2 == []  # nothing changed — no re-reads


async def test_sync_only_rereads_the_changed_file(fixture_project):
    index = SearchIndex("proj-sem-3", embedding_dim=3)
    await index.sync(fixture_project, _fake_embed)

    # Touch only Footer.tsx.
    footer = fixture_project / "src" / "components" / "Footer.tsx"
    footer.write_text(footer.read_text(encoding="utf-8") + "\n// updated\n", encoding="utf-8")

    seen: list[str] = []
    await index.sync(fixture_project, _fake_embed, _read_files_seen=seen)
    assert seen == ["src/components/Footer.tsx"]


async def test_search_returns_empty_when_nothing_indexed_yet(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "projects_dir", tmp_path / "projects")
    index = SearchIndex("proj-empty", embedding_dim=3)
    results = await index.search("anything", _fake_embed)
    assert results == []
