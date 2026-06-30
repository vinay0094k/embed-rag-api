from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.exception_handlers import register_exception_handlers
from app.core.middleware import RequestTracingMiddleware
from app.core.rate_limiter import RateLimitMiddleware
from app.db.database import init_db
from app.api.v1.router import router

# Setup structured logging
setup_logging(settings.DEBUG and "DEBUG" or "INFO")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    init_db()

    # Re-apply logging config (Alembic's fileConfig can override root logger)
    setup_logging(settings.DEBUG and "DEBUG" or "INFO")

    # Initialize background task queue
    from app.tasks.background import get_task_queue
    task_queue = get_task_queue()
    logger.info("Background task queue initialized")

    logger.info("RAG API started successfully")
    yield

    # Shutdown
    logger.info("Shutting down RAG API")
    from app.tasks.background import shutdown_tasks
    shutdown_tasks()
    logger.info("Background tasks shut down")

    # Close async HTTP client
    from app.services.embedding_service import close_async_client
    await close_async_client()
    logger.info("Async HTTP client closed")


app = FastAPI(
    title=settings.API_TITLE,
    description=settings.API_DESCRIPTION,
    version=settings.API_VERSION,
    lifespan=lifespan
)

# Register exception handlers (must be before middleware)
register_exception_handlers(app)

# Add middlewares (order matters - innermost first)
app.add_middleware(RequestTracingMiddleware)
app.add_middleware(RateLimitMiddleware)

# CORS Configuration - use specific origins in production
cors_origins = ["*"] if settings.DEBUG else settings.CORS_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=not settings.DEBUG,  # Only allow credentials in specific origins
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include v1 routes
app.include_router(router)


@app.get("/")
def root():
    """API root endpoint."""
    return {
        "name": settings.API_TITLE,
        "version": settings.API_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_level="info"
    )
