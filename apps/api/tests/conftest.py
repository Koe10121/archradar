"""Pytest fixtures for ArchRadar backend tests."""

from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

import app.models  # noqa: F401
from app.core.config import Settings
from app.db.base import Base


@pytest.fixture
async def sqlite_engine() -> AsyncIterator[AsyncEngine]:
    """Provide a clean in-memory SQLite async engine with all schema tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def test_settings() -> Settings:
    """Provide deterministic test settings without external side effects."""
    return Settings(
        environment="test",
        log_level="WARNING",
        database_url="sqlite+aiosqlite:///:memory:",
        cors_origins="http://localhost:3000",
    )
