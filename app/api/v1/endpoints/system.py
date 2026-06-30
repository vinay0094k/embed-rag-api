"""System information endpoint for exposing API configuration."""

from fastapi import APIRouter, Depends
from app.core.security import get_current_user
from app.core.config import settings

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/info")
async def get_system_info(current_user = Depends(get_current_user)):
    """
    Return system configuration including embeddings provider and model.

    Returns:
        - embeddings_provider: "local" or "openrouter" or other
        - embeddings_model: The model name/identifier
        - api_version: API version string
        - vector_store: Type of vector store (e.g., "chroma")
        - bm25_enabled: Whether BM25 indexing is enabled
    """
    return {
        "embeddings_provider": settings.EMBEDDINGS_PROVIDER,
        "embeddings_model": settings.EMBEDDINGS_MODEL,
        "api_version": "1.0.0",
        "vector_store": "chroma",
        "bm25_enabled": True
    }
