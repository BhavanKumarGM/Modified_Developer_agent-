"""
WebForge AI — FastAPI Backend
All AI inference → LLMService → Ollama → localhost:11434
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.llm_service import llm_service
from app.core.logging_context import MessageIdFilter
from app.database.database import init_db
from app.orchestrator.orchestrator import orchestrator
from app.routers import projects, chat, files, upload, preview, git, ollama

# %(message_id)s is the per-turn correlation id (Orchestrator.handle_message
# sets it) — every log line from planner/agents/git/WS events during one
# chat turn shares it, so `grep <message_id>` traces that turn end-to-end
# regardless of which module logged the line.
_log_handler = logging.StreamHandler()
_log_handler.addFilter(MessageIdFilter())
_log_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(message_id)s] — %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[_log_handler])
logger = logging.getLogger("webforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database…")
    await init_db()
    logger.info(f"WebForge AI backend ready — bound to {settings.host}:{settings.port}")
    if settings.host == "0.0.0.0":
        logger.warning(
            "⚠ Backend is reachable from the network (HOST=0.0.0.0). "
            "There is no authentication. Only do this on a trusted network."
        )
    yield
    logger.info("Shutting down…")
    await orchestrator.preview.stop_all()
    await llm_service.close()
    logger.info("Shutdown complete: preview processes terminated, LLM client closed.")


app = FastAPI(
    title="WebForge AI",
    description="Local-first AI Website Development Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(projects.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(preview.router, prefix="/api")
app.include_router(git.router, prefix="/api")
app.include_router(ollama.router, prefix="/api")


# ─── WebSocket Connection Manager ─────────────────────────────────────────────

class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, project_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.setdefault(project_id, []).append(ws)
        logger.info(f"WS connected: {project_id}")

    def disconnect(self, project_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(project_id, [])
        if ws in conns:
            conns.remove(ws)
        logger.info(f"WS disconnected: {project_id}")

    async def broadcast(self, project_id: str, event_type: str, payload: dict) -> None:
        message = json.dumps({"type": event_type, "payload": payload})
        dead: list[WebSocket] = []
        for ws in self._connections.get(project_id, []):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(project_id, ws)


manager = ConnectionManager()


@app.websocket("/ws/{project_id}")
async def websocket_endpoint(websocket: WebSocket, project_id: str):
    await manager.connect(project_id, websocket)

    def event_callback(event_type: str, payload: dict) -> None:
        asyncio.create_task(manager.broadcast(project_id, event_type, payload))

    orchestrator.register_callback(project_id, event_callback)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                msg_type = msg.get("type")
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif msg_type == "stop":
                    cancelled = orchestrator.cancel_active_task(project_id)
                    await websocket.send_text(
                        json.dumps({"type": "stop_ack", "payload": {"cancelled": cancelled}})
                    )
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        orchestrator.unregister_callback(project_id, event_callback)
        manager.disconnect(project_id, websocket)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "WebForge AI"}


if __name__ == "__main__":
    # Preferred way to run the backend: `python -m app.main`. This binds to
    # settings.host/settings.port (127.0.0.1 by default, overridable via the
    # HOST/PORT env vars) so the "what is this bound to" log line in
    # `lifespan` above is always accurate. Running uvicorn directly with an
    # explicit --host still works, but then you own keeping it in sync.
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
