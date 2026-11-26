"""FastAPI application entrypoint and factory."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

import app.models as _models  # noqa: F401
from app.api.routes.analyses import router as analyses_router
from app.api.routes.health import router as health_router
from app.api.routes.repos import router as repos_router
from app.api.routes.telemetry import router as telemetry_router
from app.api.routes.webhooks import router as webhooks_router
from app.core.config import Settings, get_settings
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.db.base import Base
from app.db.session import create_db_engine, create_session_factory
from app.services.ai_analyzer import LLMProvider
from app.services.demo_seeder import seed_demo_data

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    db_engine: AsyncEngine | None = None,
    llm_provider: LLMProvider | None = None,
) -> FastAPI:
    """Create and configure a FastAPI application instance."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    owns_engine = db_engine is None
    resolved_engine = db_engine or create_db_engine(resolved_settings.database_url)
    bootstrap_lock = asyncio.Lock()
    bootstrap_done = False

    async def ensure_bootstrapped(application: FastAPI) -> None:
        nonlocal bootstrap_done
        if bootstrap_done:
            return
        async with bootstrap_lock:
            if bootstrap_done:
                return
            if resolved_settings.should_auto_init_db:
                try:
                    async with application.state.db_engine.begin() as conn:
                        await conn.run_sync(Base.metadata.create_all)
                except Exception as exc:
                    logger.warning(
                        "Automatic DB table initialization skipped (%s: %s)",
                        type(exc).__name__,
                        exc,
                        exc_info=True,
                    )
            if resolved_settings.seed_demo_on_startup:
                try:
                    session_factory = create_session_factory(application.state.db_engine)
                    async with session_factory() as session:
                        summary = await seed_demo_data(session)
                    logger.info(
                        "Demo startup seed complete (repos_created=%d, analyses_created=%d)",
                        summary.repos_created,
                        summary.analyses_created,
                    )
                except Exception as exc:
                    logger.warning(
                        "Demo startup seed skipped (%s: %s)",
                        type(exc).__name__,
                        exc,
                        exc_info=True,
                    )
            bootstrap_done = True

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        await ensure_bootstrapped(application)
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
    application.state.llm_provider = llm_provider

    @application.middleware("http")
    async def _lazy_serverless_bootstrap(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not bootstrap_done and (
            resolved_settings.should_auto_init_db or resolved_settings.seed_demo_on_startup
        ):
            await ensure_bootstrapped(application)
        return await call_next(request)

    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/")
    async def root_status() -> dict[str, str]:
        return {
            "service": resolved_settings.app_name,
            "version": resolved_settings.app_version,
            "status": "ok",
            "health": "/api/health",
        }

    application.include_router(health_router)
    application.include_router(repos_router)
    application.include_router(analyses_router)
    application.include_router(telemetry_router)
    application.include_router(webhooks_router)
    return application


app = create_app()
