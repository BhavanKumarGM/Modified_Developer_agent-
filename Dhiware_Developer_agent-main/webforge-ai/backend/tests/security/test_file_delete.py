"""Tests for POST /api/files/delete (audit item 3.2): must actually delete
the file, and must reject path traversal the same way read/write do.
"""
from pathlib import Path

import pytest


async def test_delete_happy_path(client, project):
    write_resp = await client.post(
        "/api/files/write",
        json={"projectId": project["id"], "path": "src/Obsolete.tsx", "content": "x"},
    )
    assert write_resp.status_code == 200

    root = Path(project["rootPath"])
    assert (root / "src" / "Obsolete.tsx").exists()

    delete_resp = await client.post(
        "/api/files/delete", json={"projectId": project["id"], "path": "src/Obsolete.tsx"}
    )
    assert delete_resp.status_code == 200
    assert not (root / "src" / "Obsolete.tsx").exists()


async def test_delete_nonexistent_file_returns_404(client, project):
    resp = await client.post(
        "/api/files/delete", json={"projectId": project["id"], "path": "src/DoesNotExist.tsx"}
    )
    assert resp.status_code == 404


@pytest.mark.parametrize("bad_path", ["../../../etc/passwd", "/etc/passwd"])
async def test_delete_rejects_traversal(client, project, tmp_path, bad_path):
    canary = tmp_path / "canary_secret.txt"
    canary.write_text("do-not-delete-me")

    resp = await client.post(
        "/api/files/delete", json={"projectId": project["id"], "path": bad_path}
    )
    assert resp.status_code == 400
    assert canary.exists()
    assert canary.read_text() == "do-not-delete-me"
