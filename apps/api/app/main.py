"""FastAPI application entrypoint and factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.routes.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.db.session import create_db_engine


def create_app(
    settings: Settings | None = None,
    db_engine: AsyncEngine | None = None,
) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    owns_engine = db_engine is None
    resolved_engine = db_engine or create_db_engine(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_engine:
            await application.state.db_engine.dispose()

    application = FastAPI(
        title="ArchRadar API",
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.db_engine = resolved_engine

    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    return application


app = create_app()
