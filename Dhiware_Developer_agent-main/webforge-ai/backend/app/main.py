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
from app.database.database import init_db
from app.orchestrator.orchestrator import orchestrator
from app.routers import projects, chat, files, upload, preview, git, ollama

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("webforge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database…")
    await init_db()
    logger.info("WebForge AI backend ready.")
    yield
    logger.info("Shutting down…")


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
            # Handle client messages if needed (e.g., stop signal)
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
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
