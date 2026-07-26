from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services import project_service
from app.agents.base_agent import AgentContext
from app.orchestrator.orchestrator import orchestrator

router = APIRouter(prefix="/preview", tags=["preview"])


@router.post("/start/{project_id}")
async def start_preview(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    root_path = project.get("rootPath")
    if not root_path:
        raise HTTPException(status_code=400, detail="Project has no files yet. Generate code first.")

    from pathlib import Path
    root = Path(root_path)
    if not root.exists() or not any(root.iterdir()):
        raise HTTPException(status_code=400, detail="Project directory is empty. Generate code first.")

    context = AgentContext(
        project_id=project_id,
        project_name=project["name"],
        framework=project.get("framework", "unknown"),
        root_path=root_path,
    )

    # This can take 2+ minutes on first run (npm install)
    result = await orchestrator.preview.run("start", context, action="start")

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error or "Failed to start preview")

    port = result.data.get("port")
    url = result.data.get("url")
    await project_service.update_project(db, project_id, preview_port=port)

    return {
        "port": port,
        "url": url,
        "backendPort": result.data.get("backendPort"),
        "backendUrl": result.data.get("backendUrl"),
        "backendFramework": result.data.get("backendFramework") or result.data.get("framework"),
    }


@router.post("/stop/{project_id}")
async def stop_preview(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    context = AgentContext(
        project_id=project_id,
        project_name=project["name"],
        framework=project.get("framework", "unknown"),
    )
    await orchestrator.preview.run("stop", context, action="stop")
    await project_service.update_project(db, project_id, preview_port=None)
    return {"ok": True}
