"""Regression test for audit item 5.1 at the SearchAgent level: a
semantically-phrased query (sharing no literal keywords with the target
file) must still surface that file, via the real semantic-search code path
merged with the existing keyword heuristic.
"""
import pytest

from app.agents.base_agent import AgentContext
from app.agents.search_agent import SearchAgent
from app.core.llm_service import LLMService


async def _fake_embed(text: str) -> list[float]:
    if "grandTotalWithTax" in text or "checkout basket total" in text.lower():
        return [1.0, 0.0, 0.0]
    return [0.0, 1.0, 0.0]


@pytest.fixture()
def fixture_project(tmp_path, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "projects_dir", tmp_path / "projects")
    monkeypatch.setattr(settings, "embedding_dim", 3)

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


async def test_semantic_query_surfaces_file_with_no_keyword_overlap(fixture_project, monkeypatch):
    agent = SearchAgent(LLMService())
    monkeypatch.setattr(agent.llm, "embed", _fake_embed)

    context = AgentContext(project_id="proj-search-1", project_name="Test", root_path=str(fixture_project))
    result = await agent.run("what computes the checkout basket total", context)

    files = result.data["files"]
    assert "src/utils/pricing.ts" in files
    # It should be ranked at or near the top, since semantic hits are
    # merged in ahead of the (here, non-matching) keyword heuristic.
    assert files.index("src/utils/pricing.ts") == 0


async def test_semantic_search_failure_falls_back_to_keyword_only(fixture_project, monkeypatch):
    """If the embedding model isn't pulled/Ollama is down, search must not
    fail outright — it should silently fall back to keyword/glob results."""
    agent = SearchAgent(LLMService())

    async def broken_embed(text: str):
        raise ConnectionError("Ollama unreachable")

    monkeypatch.setattr(agent.llm, "embed", broken_embed)

    context = AgentContext(project_id="proj-search-2", project_name="Test", root_path=str(fixture_project))
    result = await agent.run("dashboard", context)

    assert result.success is True
    assert isinstance(result.data["files"], list)
