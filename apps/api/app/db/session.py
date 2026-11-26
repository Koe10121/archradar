"""Async SQLAlchemy engine, session factory, and health check helper."""

import asyncio
import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)


def create_db_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine appropriate for the given URL."""
    if database_url.startswith("sqlite"):
        return create_async_engine(database_url, echo=False)
    return create_async_engine(database_url, echo=False, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the provided engine."""
    return async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Yield an async database session for request-scoped operations."""
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        yield session


async def check_database_health(
    engine: AsyncEngine,
    timeout_seconds: float = 2.0,
) -> tuple[bool, str | None]:
    """Run a lightweight connectivity check against the configured database."""

    async def _ping() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    try:
        await asyncio.wait_for(_ping(), timeout=timeout_seconds)
        return True, None
    except Exception as exc:
        logger.error(
            "Database health check failed: %s",
            type(exc).__name__,
            exc_info=True,
        )
        return False, type(exc).__name__
