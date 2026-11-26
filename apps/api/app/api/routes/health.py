"""Health endpoint for service and database connectivity verification."""

from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Request
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.core.logging import correlation_id_ctx
from app.db.session import check_database_health
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def get_health(request: Request) -> HealthResponse:
    """Return service metadata and live database connectivity status."""
    settings = cast(Settings, request.app.state.settings)
    engine = cast(AsyncEngine, request.app.state.db_engine)
    db_ok, _ = await check_database_health(engine)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database="connected" if db_ok else "unavailable",
        timestamp=datetime.now(UTC),
        correlation_id=correlation_id_ctx.get(),
    )
