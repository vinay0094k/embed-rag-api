import logging
import json
import uuid
import sys
from datetime import datetime
from typing import Any, Dict
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar('request_id', default='')


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_context.get(),
        }

        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'endpoint'):
            log_data["endpoint"] = record.endpoint
        if hasattr(record, 'duration_ms'):
            log_data["duration_ms"] = record.duration_ms

        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO"):
    """Setup structured logging. Configures root logger + all app loggers."""
    log_level_num = getattr(logging, log_level)

    root = logging.getLogger()
    root.setLevel(log_level_num)

    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)

    for name in logging.root.manager.loggerDict:
        logger = logging.getLogger(name)
        logger.propagate = True
        logger.setLevel(logging.NOTSET)

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a logger. Returns plain Logger (not Adapter) so extra= works."""
    return logging.getLogger(name)


def set_request_id(request_id: str = None):
    if request_id is None:
        request_id = str(uuid.uuid4())
    request_id_context.set(request_id)
    return request_id


def get_request_id() -> str:
    return request_id_context.get()
