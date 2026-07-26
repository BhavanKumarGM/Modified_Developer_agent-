"""Router-level tests for POST /api/upload/github (audit-style coverage,
matching test_upload_router.py's ZIP-upload tests).

clone_repo is mocked throughout — these tests must never touch the network
or a real git binary in CI. See tests/unit/test_github_service.py for the
URL-validation unit tests that back the security guarantee here.
"""
from pathlib import Path

import app.routers.upload as upload_module


def _fake_clone_writes_a_file(url: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "README.md").write_text("# Cloned project\n", encoding="utf-8")
    (dest / "src").mkdir(exist_ok=True)
    (dest / "src" / "App.tsx").write_text("export default function App() { return null }\n", encoding="utf-8")


async def test_import_github_creates_project_and_clones_files(client, tmp_projects_dir, monkeypatch):
    monkeypatch.setattr(upload_module, "clone_repo", _fake_clone_writes_a_file)

    resp = await client.post("/api/upload/github", json={"url": "https://github.com/facebook/react"})

    assert resp.status_code == 200
    project = resp.json()
    assert project["name"]
    assert project["status"] == "ready"
    root = Path(project["rootPath"])
    assert (root / "README.md").exists()
    assert (root / "src" / "App.tsx").exists()


async def test_import_github_rejects_invalid_url_without_cloning(client, monkeypatch):
    calls = []
    monkeypatch.setattr(upload_module, "clone_repo", lambda url, dest: calls.append(url))

    resp = await client.post("/api/upload/github", json={"url": "https://evil.com/owner/repo"})

    assert resp.status_code == 400
    assert calls == []  # validation must happen before any clone attempt


async def test_import_github_rejects_file_url_without_cloning(client, monkeypatch):
    calls = []
    monkeypatch.setattr(upload_module, "clone_repo", lambda url, dest: calls.append(url))

    resp = await client.post("/api/upload/github", json={"url": "file:///etc/passwd"})

    assert resp.status_code == 400
    assert calls == []


async def test_import_github_rolls_back_project_on_clone_failure(client, tmp_projects_dir, monkeypatch):
    def failing_clone(url, dest):
        raise RuntimeError("repository not found")

    monkeypatch.setattr(upload_module, "clone_repo", failing_clone)

    resp = await client.post("/api/upload/github", json={"url": "https://github.com/owner/does-not-exist"})

    assert resp.status_code == 422

    list_resp = await client.get("/api/projects")
    assert list_resp.json()["projects"] == []  # rolled back, not left dangling


async def test_import_github_infers_project_name_from_repo(client, tmp_projects_dir, monkeypatch):
    monkeypatch.setattr(upload_module, "clone_repo", _fake_clone_writes_a_file)

    resp = await client.post("/api/upload/github", json={"url": "https://github.com/facebook/react-native.git"})

    assert resp.status_code == 200
    assert resp.json()["name"] == "React Native"
