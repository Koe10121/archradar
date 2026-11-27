"""Async SQLAlchemy engine, session factory, and health check helper."""

import asyncio
import logging
import os
import ssl
from collections.abc import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

logger = logging.getLogger(__name__)

_ASYNCPG_UNSUPPORTED_PARAMS = frozenset({"sslmode", "channel_binding"})


def sanitize_asyncpg_url(database_url: str) -> tuple[str, dict[str, object]]:
    """Strip libpq-only query params (sslmode, channel_binding) into asyncpg connect_args."""
    if not database_url.startswith("postgresql+asyncpg://"):
        return database_url, {}

    parsed = urlsplit(database_url)
    connect_args: dict[str, object] = {}

    if "-pooler." in parsed.netloc.lower() or os.environ.get("VERCEL") == "1":
        connect_args["statement_cache_size"] = 0

    if not parsed.query:
        return database_url, connect_args

    raw_params = parse_qsl(parsed.query, keep_blank_values=True)
    kept_params: list[tuple[str, str]] = []

    for key, val in raw_params:
        lower_key = key.lower()
        if lower_key == "sslmode":
            mode = val.lower().strip()
            if mode == "disable":
                connect_args["ssl"] = False
            elif mode in {"require", "prefer", "allow", "verify-ca", "verify-full"}:
                connect_args["ssl"] = ssl.create_default_context()
            continue
        if lower_key in _ASYNCPG_UNSUPPORTED_PARAMS:
            continue
        kept_params.append((key, val))

    clean_url = urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(kept_params), parsed.fragment)
    )
    return clean_url, connect_args


def create_db_engine(database_url: str) -> AsyncEngine:
    """Create an async SQLAlchemy engine appropriate for the given URL."""
    if database_url.startswith("sqlite"):
        return create_async_engine(database_url, echo=False)

    clean_url, connect_args = sanitize_asyncpg_url(database_url)
    if os.environ.get("VERCEL") == "1":
        return create_async_engine(
            clean_url,
            echo=False,
            pool_size=2,
            max_overflow=3,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args=connect_args,
        )
    return create_async_engine(
        clean_url,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


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
    timeout_seconds: float = 8.0,
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
