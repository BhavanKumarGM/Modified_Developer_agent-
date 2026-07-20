"""Basic router coverage for /api/projects CRUD (audit item 6.1)."""


async def test_create_and_list_project(client):
    resp = await client.post("/api/projects", json={"name": "My App", "description": "desc"})
    assert resp.status_code == 200
    project = resp.json()
    assert project["name"] == "My App"
    assert project["status"] == "idle"

    list_resp = await client.get("/api/projects")
    assert list_resp.status_code == 200
    names = [p["name"] for p in list_resp.json()["projects"]]
    assert "My App" in names


async def test_get_project_by_id(client, project):
    resp = await client.get(f"/api/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == project["id"]


async def test_get_unknown_project_returns_404(client):
    resp = await client.get("/api/projects/does-not-exist")
    assert resp.status_code == 404


async def test_delete_project(client, project):
    resp = await client.delete(f"/api/projects/{project['id']}")
    assert resp.status_code == 200

    get_resp = await client.get(f"/api/projects/{project['id']}")
    assert get_resp.status_code == 404


async def test_delete_unknown_project_returns_404(client):
    resp = await client.delete("/api/projects/does-not-exist")
    assert resp.status_code == 404
