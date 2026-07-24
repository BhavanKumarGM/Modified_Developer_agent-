import asyncio
import uuid
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db, AsyncSessionLocal
from app.services import project_service
from app.services.zip_service import extract_zip
from app.services.github_service import InvalidGitHubUrlError, clone_repo, parse_github_url
from app.orchestrator.orchestrator import orchestrator
from app.core.config import settings

router = APIRouter(prefix="/upload", tags=["upload"])

# Real `git clone` can take a while for a large repo — bounded so a huge or
# slow-to-respond repo can't hang the request indefinitely.
GITHUB_CLONE_TIMEOUT_SECONDS = 300


class ImportGithubRequest(BaseModel):
    url: str


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


@router.post("/github")
async def upload_github(
    req: ImportGithubRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        owner, repo_name = parse_github_url(req.url)
    except InvalidGitHubUrlError as e:
        raise HTTPException(status_code=400, detail=str(e))

    name = repo_name.replace("_", " ").replace("-", " ").title()

    # Create the project record first (this allocates the id and an empty
    # root_path directory) and clone directly into it — unlike ZIP upload,
    # a real `git clone` is expensive enough that cloning once straight to
    # the final location is worth it over cloning to a temp dir and copying.
    project = await project_service.create_project(db, name)
    project_id = project["id"]
    project_root = Path(project["rootPath"])

    try:
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, clone_repo, req.url, project_root
            ),
            timeout=GITHUB_CLONE_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        await project_service.delete_project(db, project_id)
        shutil.rmtree(project_root, ignore_errors=True)
        raise HTTPException(status_code=504, detail="Cloning the repository timed out")
    except Exception as e:
        await project_service.delete_project(db, project_id)
        shutil.rmtree(project_root, ignore_errors=True)
        raise HTTPException(status_code=422, detail=f"Failed to clone repository: {e}")

    await project_service.update_project(db, project_id, status="ready")
    project["rootPath"] = str(project_root)
    project["status"] = "ready"

    # Run analysis in the background so the request returns immediately —
    # same pattern as upload_zip.
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
