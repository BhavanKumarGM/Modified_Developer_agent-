from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.database import get_db, AsyncSessionLocal
from app.services import project_service
from app.orchestrator.orchestrator import orchestrator

router = APIRouter(prefix="/chat", tags=["chat"])


class SendMessageRequest(BaseModel):
    projectId: str
    message: str


@router.post("/send")
async def send_message(
    req: SendMessageRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    project = await project_service.get_project(db, req.projectId)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save user message
    await project_service.add_message(db, req.projectId, "user", req.message)

    # Create placeholder assistant message
    assistant_msg = await project_service.add_message(db, req.projectId, "assistant", "")
    message_id = assistant_msg["id"]

    # Snapshot conversation history before closing request session
    history = await project_service.get_messages(db, req.projectId)
    conversation_history = [
        {"role": m["role"], "content": m["content"]}
        for m in history[:-1]
        if m["content"]
    ]

    # Capture project data needed by the pipeline
    project_snapshot = dict(project)

    async def run_pipeline():
        full_content = ""
        async for token in orchestrator.handle_message(
            project_id=req.projectId,
            project_name=project_snapshot["name"],
            framework=project_snapshot.get("framework", "unknown"),
            root_path=project_snapshot.get("rootPath"),
            metadata=project_snapshot.get("metadata", {}),
            conversation_history=conversation_history,
            user_message=req.message,
            message_id=message_id,
        ):
            full_content += token

        # Persist final content with its own session
        async with AsyncSessionLocal() as session:
            await project_service.update_message_content(session, message_id, full_content)

    background_tasks.add_task(run_pipeline)

    return {"messageId": message_id}


@router.get("/history/{project_id}")
async def get_history(project_id: str, db: AsyncSession = Depends(get_db)):
    messages = await project_service.get_messages(db, project_id)
    return {"messages": messages}
