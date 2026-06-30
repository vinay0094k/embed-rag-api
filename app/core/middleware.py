import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import set_request_id, get_request_id, get_logger

logger = get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request tracing with unique request IDs."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID")
        set_request_id(request_id)

        request.state.request_id = get_request_id()

        start_time = time.time()
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={
                "endpoint": request.url.path,
                "method": request.method,
                "client": request.client.host if request.client else "unknown"
            }
        )

        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000

        response.headers["X-Request-ID"] = request.state.request_id

        log_level = "info" if response.status_code < 400 else "warning"
        logger_method = getattr(logger, log_level)
        logger_method(
            f"← {request.method} {request.url.path} {response.status_code}",
            extra={
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": f"{duration_ms:.2f}"
            }
        )

        return response
