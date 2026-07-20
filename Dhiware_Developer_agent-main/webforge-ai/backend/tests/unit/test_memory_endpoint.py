"""GET /api/projects/{id}/memory — the endpoint MemoryPanel.tsx now reads
from (audit item 2.3), replacing a panel that previously pointed at nothing.
"""
import json


async def test_memory_endpoint_returns_empty_dict_for_fresh_project(client, project):
    resp = await client.get(f"/api/projects/{project['id']}/memory")
    assert resp.status_code == 200
    assert resp.json() == {"memory": {}}


async def test_memory_endpoint_returns_stored_metadata(client, project, test_engine):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.database.models import ProjectModel

    test_session_local = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)
    async with test_session_local() as session:
        result = await session.execute(select(ProjectModel).where(ProjectModel.id == project["id"]))
        p = result.scalar_one()
        p.metadata_json = json.dumps({"theme": "dark"})
        await session.commit()

    resp = await client.get(f"/api/projects/{project['id']}/memory")
    assert resp.status_code == 200
    assert resp.json() == {"memory": {"theme": "dark"}}


async def test_memory_endpoint_404_for_unknown_project(client):
    resp = await client.get("/api/projects/does-not-exist/memory")
    assert resp.status_code == 404
