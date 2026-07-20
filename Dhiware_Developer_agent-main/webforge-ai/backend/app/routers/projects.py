from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    description: Optional[str] = None


@router.get("")
async def list_projects(db: AsyncSession = Depends(get_db)):
    projects = await project_service.list_projects(db)
    return {"projects": projects}


@router.post("")
async def create_project(req: CreateProjectRequest, db: AsyncSession = Depends(get_db)):
    return await project_service.create_project(db, req.name, req.description)


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}")
async def delete_project(project_id: str, db: AsyncSession = Depends(get_db)):
    ok = await project_service.delete_project(db, project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}


@router.get("/{project_id}/memory")
async def get_project_memory(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"memory": project.get("metadata") or {}}
