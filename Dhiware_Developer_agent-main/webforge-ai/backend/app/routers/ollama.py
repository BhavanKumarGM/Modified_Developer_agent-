from fastapi import APIRouter
from app.core.llm_service import llm_service

router = APIRouter(prefix="/ollama", tags=["ollama"])


@router.get("/status")
async def ollama_status():
    connected = await llm_service.health_check()
    models = await llm_service.list_models() if connected else []
    return {"connected": connected, "models": models}
