from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services import project_service

router = APIRouter(prefix="/git", tags=["git"])


class RestoreRequest(BaseModel):
    projectId: str
    snapshotId: str


@router.get("/history/{project_id}")
async def get_history(project_id: str, db: AsyncSession = Depends(get_db)):
    snapshots = await project_service.get_snapshots(db, project_id)
    return {"snapshots": snapshots}


@router.post("/restore")
async def restore_snapshot(req: RestoreRequest, db: AsyncSession = Depends(get_db)):
    # Future: implement full git restore using gitpython
    return {"ok": True, "message": "Restore queued"}
