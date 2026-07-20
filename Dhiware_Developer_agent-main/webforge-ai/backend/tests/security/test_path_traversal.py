"""Regression tests for path traversal on /api/files/read and /api/files/write.

Before the fix, both endpoints did `root / req.path` with no containment
check, so `path="../../../etc/passwd"` (or a Windows equivalent) would read
or write outside the project root.
"""
from pathlib import Path

import pytest

TRAVERSAL_PATHS = [
    "../../../etc/passwd",
    "..\\..\\..\\Windows\\System32\\config\\SAM",
    "/etc/passwd",
]


@pytest.mark.parametrize("bad_path", TRAVERSAL_PATHS)
async def test_read_file_rejects_traversal(client, project, tmp_path, bad_path):
    # Plant a canary file outside the project root to prove it's never touched.
    canary = tmp_path / "canary_secret.txt"
    canary.write_text("do-not-read-me")

    resp = await client.post(
        "/api/files/read", json={"projectId": project["id"], "path": bad_path}
    )
    assert resp.status_code == 400
    assert canary.read_text() == "do-not-read-me"


@pytest.mark.parametrize("bad_path", TRAVERSAL_PATHS)
async def test_write_file_rejects_traversal(client, project, tmp_path, bad_path):
    resp = await client.post(
        "/api/files/write",
        json={"projectId": project["id"], "path": bad_path, "content": "pwned"},
    )
    assert resp.status_code == 400

    # Nothing was written anywhere outside the project root.
    root = Path(project["rootPath"])
    for suspicious in [tmp_path / "etc" / "passwd", tmp_path.parent / "pwned"]:
        assert not suspicious.exists()
    # And the project root itself only ever contains what the fixture put there.
    assert not any(root.rglob("passwd"))
    assert not any(root.rglob("SAM"))


async def test_read_write_roundtrip_still_works(client, project):
    """Sanity check: the safety fix must not break legitimate paths."""
    write_resp = await client.post(
        "/api/files/write",
        json={"projectId": project["id"], "path": "src/App.tsx", "content": "hello"},
    )
    assert write_resp.status_code == 200

    read_resp = await client.post(
        "/api/files/read", json={"projectId": project["id"], "path": "src/App.tsx"}
    )
    assert read_resp.status_code == 200
    assert read_resp.json()["content"] == "hello"
