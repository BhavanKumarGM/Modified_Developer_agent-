"""Shared pytest fixtures for the backend test suite.

Tests never touch the real webforge.db or the real projects/ directory —
every test gets its own temp SQLite DB and its own temp projects dir via
these fixtures.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.database.database as db_module
from app.core.config import settings
from app.database.database import Base
import app.database.models  # noqa: F401 — registers tables on Base.metadata


@pytest.fixture()
def tmp_projects_dir(tmp_path, monkeypatch):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    monkeypatch.setattr(settings, "projects_dir", projects_dir)
    return projects_dir


@pytest.fixture()
async def test_engine(tmp_path):
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    # Create the schema with a plain sync engine first — DDL doesn't need to
    # be async, and doing it synchronously avoids any race between the
    # async "create tables" connection and the async connections opened
    # later by the app against the same file.
    sync_engine = create_engine(db_url)
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    yield engine
    await engine.dispose()


@pytest.fixture()
async def client(test_engine, tmp_projects_dir):
    """An httpx.AsyncClient wired to the real FastAPI app, but with the DB
    dependency overridden to a per-test temp SQLite engine."""
    test_session_local = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)

    async def override_get_db():
        async with test_session_local() as session:
            try:
                yield session
            finally:
                await session.close()

    from app.main import app

    app.dependency_overrides[db_module.get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
async def project(client):
    """Create a project through the real API and return its dict."""
    resp = await client.post("/api/projects", json={"name": "Test Project"})
    assert resp.status_code == 200
    return resp.json()
