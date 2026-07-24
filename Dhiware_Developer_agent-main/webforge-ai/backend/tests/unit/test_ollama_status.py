"""Regression tests for /api/ollama/status's model-availability fields.

Before this fix, the endpoint only reported whether the Ollama *server*
was reachable, never whether the specific model this app needs
(settings.default_model / settings.embedding_model) was actually pulled.
Ollama being up with the wrong models pulled looked identical to
everything being ready — the mismatch only surfaced later as an opaque
failure deep inside a chat turn.
"""
import pytest

from app.core.llm_service import model_name_matches


@pytest.mark.parametrize(
    "target,available,expected",
    [
        ("qwen2.5-coder:7b", ["qwen2.5-coder:7b"], True),
        ("qwen2.5-coder:7b", ["mistral:latest"], False),
        # bare (untagged) config value must match any tag of that model
        ("nomic-embed-text", ["nomic-embed-text:latest"], True),
        ("nomic-embed-text", ["nomic-embed-text:v1.5"], True),
        ("nomic-embed-text", [], False),
        # a tagged target must NOT loosely match an unrelated model whose
        # name happens to be a prefix
        ("qwen2.5-coder:7b", ["qwen2.5-coder:14b"], False),
    ],
)
def test_model_name_matches(target, available, expected):
    assert model_name_matches(target, available) is expected


async def test_status_endpoint_reports_model_availability(client, monkeypatch):
    import app.routers.ollama as ollama_module

    async def fake_health_check():
        return True

    async def fake_list_models():
        return ["qwen2.5-coder:7b", "mistral:latest"]  # embedding model NOT pulled

    monkeypatch.setattr(ollama_module.llm_service, "health_check", fake_health_check)
    monkeypatch.setattr(ollama_module.llm_service, "list_models", fake_list_models)
    monkeypatch.setattr(ollama_module.settings, "default_model", "qwen2.5-coder:7b")
    monkeypatch.setattr(ollama_module.settings, "embedding_model", "nomic-embed-text")

    resp = await client.get("/api/ollama/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["default_model_available"] is True
    assert body["embedding_model_available"] is False


async def test_status_endpoint_when_ollama_unreachable(client, monkeypatch):
    import app.routers.ollama as ollama_module

    async def fake_health_check():
        return False

    monkeypatch.setattr(ollama_module.llm_service, "health_check", fake_health_check)

    resp = await client.get("/api/ollama/status")

    body = resp.json()
    assert body["connected"] is False
    assert body["default_model_available"] is False
    assert body["embedding_model_available"] is False
