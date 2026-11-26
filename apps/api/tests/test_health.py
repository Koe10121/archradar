"""Health endpoint and schema metadata tests."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings
from app.db.base import Base
from app.main import create_app
from app.schemas.health import HealthResponse


async def test_health_endpoint_connected(
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """GET /api/health returns ok and echoes correlation ID when DB is reachable."""
    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health", headers={"X-Correlation-ID": "corr-123"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-123"
    payload = HealthResponse.model_validate(response.json())
    assert payload.status == "ok"
    assert payload.database == "connected"
    assert payload.service == "archradar-api"
    assert payload.environment == "test"
    assert payload.correlation_id == "corr-123"


async def test_health_endpoint_database_unavailable(
    test_settings: Settings,
) -> None:
    """GET /api/health reports degraded when database connectivity fails."""
    failing_engine = create_async_engine(
        "sqlite+aiosqlite:///./nonexistent_dir_archradar/missing.db",
        echo=False,
    )
    app = create_app(settings=test_settings, db_engine=failing_engine)
    transport = httpx.ASGITransport(app=app)

    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/health")
    finally:
        await failing_engine.dispose()

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"]
    payload = HealthResponse.model_validate(response.json())
    assert payload.status == "degraded"
    assert payload.database == "unavailable"


def test_metadata_tables_created() -> None:
    """All core architecture tables are registered on SQLAlchemy metadata."""
    expected_tables = {
        "repositories",
        "graph_snapshots",
        "file_nodes",
        "dependency_edges",
        "pr_analyses",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))
