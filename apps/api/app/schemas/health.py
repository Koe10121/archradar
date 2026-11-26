"""Health check response contract shared with apps/web."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Service and database readiness payload."""

    status: Literal["ok", "degraded"]
    service: str
    version: str
    environment: str
    database: Literal["connected", "unavailable"]
    timestamp: datetime
    correlation_id: str
