import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.rate_limiter import RateLimiter
from app.database.database import get_db, AsyncSessionLocal
from app.services import project_service
from app.orchestrator.orchestrator import orchestrator

router = APIRouter(prefix="/chat", tags=["chat"])

# Keyed by project_id — a single project being spammed shouldn't starve
# others, and a single-user local tool has no need for a global limit.
_chat_rate_limiter = RateLimiter(max_requests=settings.chat_rate_limit_per_minute)


class SendMessageRequest(BaseModel):
    projectId: str
    message: str


@router.post("/send")
async def send_message(
    req: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
):
    if len(req.message) > settings.max_message_length:
        raise HTTPException(
            status_code=400,
            detail=f"Message too long ({len(req.message)} chars, max {settings.max_message_length})",
        )
    if not _chat_rate_limiter.allow(req.projectId):
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests — max {settings.chat_rate_limit_per_minute} per minute per project",
        )

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
        cancelled = False
        try:
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
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            # Persist whatever was generated so far, even on cancellation —
            # partial output is still useful and the message row shouldn't
            # be left as an empty placeholder forever.
            async with AsyncSessionLocal() as session:
                await project_service.update_message_content(session, message_id, full_content)
            if cancelled:
                orchestrator._emit(req.projectId, "stream_cancelled", {"messageId": message_id})
            orchestrator.unregister_task(req.projectId, task)

    task = asyncio.create_task(run_pipeline())
    orchestrator.register_task(req.projectId, task)

    return {"messageId": message_id}


@router.get("/history/{project_id}")
async def get_history(project_id: str, db: AsyncSession = Depends(get_db)):
    messages = await project_service.get_messages(db, project_id)
    return {"messages": messages}
