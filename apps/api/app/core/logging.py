"""Structured JSON logging and correlation ID middleware."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")


class StructuredJsonFormatter(logging.Formatter):
    """Format log records as single-line JSON with correlation ID context."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": correlation_id_ctx.get(),
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with structured JSON formatting."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredJsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(numeric_level)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Attach a per-request correlation ID to contextvars and response headers."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or uuid4().hex
        token = correlation_id_ctx.set(correlation_id)
        try:
            response = await call_next(request)
        finally:
            correlation_id_ctx.reset(token)
        response.headers["X-Correlation-ID"] = correlation_id
        return response
