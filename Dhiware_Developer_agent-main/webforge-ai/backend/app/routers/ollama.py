from fastapi import APIRouter

from app.core.config import settings
from app.core.llm_service import llm_service, model_name_matches

router = APIRouter(prefix="/ollama", tags=["ollama"])


@router.get("/status")
async def ollama_status():
    connected = await llm_service.health_check()
    models = await llm_service.list_models() if connected else []
    return {
        "connected": connected,
        "models": models,
        # The server being reachable doesn't mean the model this app
        # actually needs is pulled — without these, a missing model only
        # surfaces as an opaque failure deep inside a chat turn instead of
        # an upfront "ollama pull ..." warning.
        "default_model_available": model_name_matches(settings.default_model, models),
        "embedding_model_available": model_name_matches(settings.embedding_model, models),
    }
