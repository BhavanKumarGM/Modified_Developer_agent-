"""Project CRUD and business logic."""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ProjectModel, MessageModel, SnapshotModel
from app.core.config import settings


def _to_dict(project: ProjectModel) -> dict:
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "framework": project.framework,
        "status": project.status,
        "rootPath": project.root_path,
        "previewPort": project.preview_port,
        "metadata": project.metadata_dict,
        "createdAt": project.created_at.isoformat(),
        "updatedAt": project.updated_at.isoformat(),
    }


async def list_projects(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(ProjectModel).order_by(ProjectModel.created_at.desc())
    )
    return [_to_dict(p) for p in result.scalars().all()]


async def get_project(db: AsyncSession, project_id: str) -> Optional[dict]:
    result = await db.execute(select(ProjectModel).where(ProjectModel.id == project_id))
    p = result.scalar_one_or_none()
    return _to_dict(p) if p else None


async def get_project_model(db: AsyncSession, project_id: str) -> Optional[ProjectModel]:
    result = await db.execute(select(ProjectModel).where(ProjectModel.id == project_id))
    return result.scalar_one_or_none()


async def create_project(db: AsyncSession, name: str, description: Optional[str] = None) -> dict:
    project_id = str(uuid.uuid4())
    root_path = settings.projects_dir / project_id
    root_path.mkdir(parents=True, exist_ok=True)

    project = ProjectModel(
        id=project_id,
        name=name,
        description=description,
        framework="unknown",
        status="idle",
        root_path=str(root_path),
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _to_dict(project)


async def update_project(db: AsyncSession, project_id: str, **kwargs) -> Optional[dict]:
    p = await get_project_model(db, project_id)
    if not p:
        return None
    for k, v in kwargs.items():
        if hasattr(p, k):
            setattr(p, k, v)
    await db.commit()
    await db.refresh(p)
    return _to_dict(p)


async def delete_project(db: AsyncSession, project_id: str) -> bool:
    p = await get_project_model(db, project_id)
    if not p:
        return False
    await db.delete(p)
    await db.commit()
    return True


async def add_message(
    db: AsyncSession,
    project_id: str,
    role: str,
    content: str,
    agent_name: Optional[str] = None,
) -> dict:
    msg = MessageModel(
        id=str(uuid.uuid4()),
        project_id=project_id,
        role=role,
        content=content,
        agent_name=agent_name,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "agentName": msg.agent_name,
        "timestamp": msg.timestamp.isoformat(),
    }


async def get_messages(db: AsyncSession, project_id: str) -> list[dict]:
    result = await db.execute(
        select(MessageModel)
        .where(MessageModel.project_id == project_id)
        .order_by(MessageModel.timestamp)
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "agentName": m.agent_name,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in result.scalars().all()
    ]


async def update_message_content(db: AsyncSession, message_id: str, content: str) -> None:
    result = await db.execute(select(MessageModel).where(MessageModel.id == message_id))
    msg = result.scalar_one_or_none()
    if msg:
        msg.content = content
        await db.commit()


async def add_snapshot(
    db: AsyncSession,
    project_id: str,
    message: str,
    files_changed: int = 0,
    additions: int = 0,
    deletions: int = 0,
) -> dict:
    snap = SnapshotModel(
        id=str(uuid.uuid4()),
        project_id=project_id,
        message=message,
        files_changed=files_changed,
        additions=additions,
        deletions=deletions,
    )
    db.add(snap)
    await db.commit()
    await db.refresh(snap)
    return {
        "id": snap.id,
        "message": snap.message,
        "filesChanged": snap.files_changed,
        "additions": snap.additions,
        "deletions": snap.deletions,
        "timestamp": snap.created_at.isoformat(),
    }


async def get_snapshots(db: AsyncSession, project_id: str) -> list[dict]:
    result = await db.execute(
        select(SnapshotModel)
        .where(SnapshotModel.project_id == project_id)
        .order_by(SnapshotModel.created_at.desc())
    )
    return [
        {
            "id": s.id,
            "message": s.message,
            "filesChanged": s.files_changed,
            "additions": s.additions,
            "deletions": s.deletions,
            "timestamp": s.created_at.isoformat(),
        }
        for s in result.scalars().all()
    ]
