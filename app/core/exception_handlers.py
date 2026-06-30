import logging
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from app.core.logging import get_request_id
from app.core.exceptions import RAGException

logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response."""

    def __init__(
        self,
        status_code: int,
        error_type: str,
        message: str,
        request_id: str = None,
        details: dict = None
    ):
        self.status_code = status_code
        self.error_type = error_type
        self.message = message
        self.request_id = request_id or get_request_id()
        self.details = details or {}

    def to_dict(self):
        return {
            "error": {
                "type": self.error_type,
                "message": self.message,
                "request_id": self.request_id,
                "details": self.details
            }
        }


async def rag_exception_handler(request: Request, exc: RAGException):
    """Handle RAG-specific exceptions."""
    logger.warning(
        f"RAG Exception: {exc.detail}",
        extra={"endpoint": request.url.path}
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            status_code=exc.status_code,
            error_type="RAGException",
            message=exc.detail,
        ).to_dict()
    )


async def validation_exception_handler(request: Request, exc: ValidationError):
    """Handle Pydantic validation errors."""
    error_details = []
    for error in exc.errors():
        error_details.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        f"Validation Error: {len(error_details)} validation errors",
        extra={"endpoint": request.url.path}
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_type="ValidationError",
            message="Request validation failed",
            details={"errors": error_details}
        ).to_dict()
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    logger.error(
        f"Database Error: {str(exc)}",
        extra={"endpoint": request.url.path},
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="DatabaseError",
            message="Database operation failed",
        ).to_dict()
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.error(
        f"Unhandled Exception: {str(exc)}",
        extra={
            "endpoint": request.url.path,
            "exception_type": type(exc).__name__
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_type="InternalServerError",
            message="An unexpected error occurred",
        ).to_dict()
    )


def register_exception_handlers(app: FastAPI):
    """Register all exception handlers with the FastAPI app."""
    app.add_exception_handler(RAGException, rag_exception_handler)
    app.add_exception_handler(ValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
