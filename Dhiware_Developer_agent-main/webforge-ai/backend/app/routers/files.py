import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db
from app.services import project_service
from app.services.file_service import build_file_tree, delete_file, read_file, write_file

router = APIRouter(prefix="/files", tags=["files"])


class ReadFileRequest(BaseModel):
    projectId: str
    path: str


class WriteFileRequest(BaseModel):
    projectId: str
    path: str
    content: str


class DeleteFileRequest(BaseModel):
    projectId: str
    path: str


@router.get("/tree/{project_id}")
async def get_file_tree(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, project_id)
    if not project or not project.get("rootPath"):
        raise HTTPException(status_code=404, detail="Project not found or has no files")

    root = Path(project["rootPath"])
    if not root.exists():
        return {"tree": []}

    tree = build_file_tree(root)
    return {"tree": tree}


@router.post("/read")
async def read_file_content(req: ReadFileRequest, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, req.projectId)
    if not project or not project.get("rootPath"):
        raise HTTPException(status_code=404, detail="Project not found")

    root = Path(project["rootPath"])
    try:
        content, language = read_file(root, req.path)
        return {"content": content, "language": language}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")


@router.get("/download/{project_id}")
async def download_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, project_id)
    if not project or not project.get("rootPath"):
        raise HTTPException(status_code=404, detail="Project not found or has no files")

    root = Path(project["rootPath"])
    if not root.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")

    SKIP_DIRS = {"node_modules", "dist", "build", ".cache", ".git", "__pycache__", ".next", ".vite"}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file():
                zf.write(path, path.relative_to(root))
    buf.seek(0)

    project_name = (project.get("name") or "project").replace(" ", "_")
    filename = f"{project_name}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/write")
async def write_file_content(req: WriteFileRequest, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, req.projectId)
    if not project or not project.get("rootPath"):
        raise HTTPException(status_code=404, detail="Project not found")

    root = Path(project["rootPath"])
    try:
        write_file(root, req.path, req.content)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/delete")
async def delete_file_content(req: DeleteFileRequest, db: AsyncSession = Depends(get_db)):
    project = await project_service.get_project(db, req.projectId)
    if not project or not project.get("rootPath"):
        raise HTTPException(status_code=404, detail="Project not found")

    root = Path(project["rootPath"])
    try:
        delete_file(root, req.path)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
