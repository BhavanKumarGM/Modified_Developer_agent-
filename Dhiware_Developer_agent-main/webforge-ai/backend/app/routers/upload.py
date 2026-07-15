import asyncio
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db, AsyncSessionLocal
from app.services import project_service
from app.services.zip_service import extract_zip
from app.orchestrator.orchestrator import orchestrator
from app.core.config import settings

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/zip")
async def upload_zip(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are accepted")

    max_size = settings.max_zip_size_mb * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.max_zip_size_mb}MB)")

    # Save ZIP to temp
    project_id = str(uuid.uuid4())
    zip_tmp = settings.projects_dir / f"{project_id}.zip"
    extract_dir = settings.projects_dir / project_id

    zip_tmp.write_bytes(content)

    try:
        extract_zip(zip_tmp, extract_dir)
    except Exception as e:
        zip_tmp.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Failed to extract ZIP: {e}")
    finally:
        zip_tmp.unlink(missing_ok=True)

    # Infer project name from filename
    name = file.filename.replace(".zip", "").replace("_", " ").replace("-", " ").title()

    # Create project record
    project = await project_service.create_project(db, name)
    project_id = project["id"]

    # Move extracted files to project dir
    project_root = settings.projects_dir / project_id
    project_root.mkdir(parents=True, exist_ok=True)
    for item in extract_dir.iterdir():
        dest = project_root / item.name
        if item.is_dir():
            shutil.copytree(str(item), str(dest), dirs_exist_ok=True)
        else:
            shutil.copy2(str(item), str(dest))
    shutil.rmtree(str(extract_dir), ignore_errors=True)

    # Update root path
    await project_service.update_project(
        db, project_id, root_path=str(project_root), status="ready"
    )

    project["rootPath"] = str(project_root)
    project["status"] = "ready"

    # Run analysis in the background so the upload response returns immediately
    async def _analyse():
        try:
            async with AsyncSessionLocal() as session:
                analysis = await orchestrator.analyze_repository(
                    project_id=project_id,
                    root_path=str(project_root),
                    project_name=name,
                )
                framework = analysis.get("framework", "unknown")
                import json as _json
                await project_service.update_project(
                    session, project_id,
                    framework=framework,
                    metadata_json=_json.dumps(analysis),
                )
        except Exception:
            pass

    asyncio.create_task(_analyse())

    return project
