import time
from fastapi import APIRouter

from app.core.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])

# Track startup time
_startup_time = time.time()


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Check API health and status."""
    uptime = int(time.time() - _startup_time)

    return HealthResponse(
        status="healthy",
        version=settings.API_VERSION,
        embeddings_model=settings.EMBEDDINGS_MODEL,
        vector_store="chroma",
        database="sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql",
        uptime_seconds=uptime
    )
