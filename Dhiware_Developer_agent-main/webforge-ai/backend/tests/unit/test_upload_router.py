"""Basic router coverage for /api/upload/zip (audit item 6.1)."""
import io
import zipfile
from pathlib import Path


def _build_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("myapp/src/App.tsx", "export default function App() { return null }")
        zf.writestr("myapp/package.json", "{}")
    return buf.getvalue()


async def test_upload_zip_creates_project_and_extracts_files(client, tmp_projects_dir):
    zip_bytes = _build_zip_bytes()

    resp = await client.post(
        "/api/upload/zip",
        files={"file": ("myapp.zip", zip_bytes, "application/zip")},
    )

    assert resp.status_code == 200
    project = resp.json()
    assert project["name"]
    assert project["rootPath"]
    assert project["status"] == "ready"

    root = Path(project["rootPath"])
    assert (root / "src" / "App.tsx").exists()
    assert (root / "package.json").exists()


async def test_upload_rejects_non_zip_file(client):
    resp = await client.post(
        "/api/upload/zip",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


async def test_upload_rejects_oversized_zip(client, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "max_zip_size_mb", 0)  # anything is "too big"

    resp = await client.post(
        "/api/upload/zip",
        files={"file": ("myapp.zip", _build_zip_bytes(), "application/zip")},
    )
    assert resp.status_code == 413
