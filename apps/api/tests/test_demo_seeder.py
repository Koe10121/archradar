"""Tests for demo repository seeder, /api/repos/{id}/analyses, and DB URL normalization."""

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.db.session import create_session_factory
from app.main import create_app
from app.schemas.analysis import PRAnalysisResponse
from app.schemas.repo import GraphResponse, RepositorySummary
from app.services.demo_seeder import (
    DEMO_BILLING_REPO_ID,
    DEMO_FULFILLMENT_REPO_ID,
    seed_demo_data,
)


def test_settings_normalizes_postgres_schemes() -> None:
    """Cloud Postgres URL schemes normalize cleanly to postgresql+asyncpg."""
    assert (
        Settings(database_url="postgres://user:pass@host:5432/db").database_url
        == "postgresql+asyncpg://user:pass@host:5432/db"
    )
    assert (
        Settings(database_url="postgresql://user:pass@host:5432/db").database_url
        == "postgresql+asyncpg://user:pass@host:5432/db"
    )
    assert (
        Settings(database_url="sqlite+aiosqlite:///./dev.db").database_url
        == "sqlite+aiosqlite:///./dev.db"
    )


async def test_demo_seeder_idempotency_and_api_endpoints(
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """seed_demo_data creates 2 repos, 2 graphs, and 3 verified PR analyses idempotently."""
    session_factory = create_session_factory(sqlite_engine)
    async with session_factory() as session:
        first = await seed_demo_data(session)
        assert first.repos_created == 2
        assert first.snapshots_created == 2
        assert first.analyses_created == 3

    async with session_factory() as session:
        second = await seed_demo_data(session)
        assert second.repos_created == 0
        assert second.snapshots_created == 0
        assert second.analyses_created == 0

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        repos_resp = await client.get("/api/repos")
        assert repos_resp.status_code == 200
        repos = [RepositorySummary.model_validate(item) for item in repos_resp.json()]
        assert len(repos) == 2
        assert all(repo.is_demo for repo in repos)
        assert {repo.id for repo in repos} == {
            DEMO_BILLING_REPO_ID,
            DEMO_FULFILLMENT_REPO_ID,
        }

        billing_graph_resp = await client.get(f"/api/repos/{DEMO_BILLING_REPO_ID}/graph")
        assert billing_graph_resp.status_code == 200
        billing_graph = GraphResponse.model_validate(billing_graph_resp.json())
        assert billing_graph.file_count == 12
        assert billing_graph.edge_count == 14

        billing_analyses_resp = await client.get(f"/api/repos/{DEMO_BILLING_REPO_ID}/analyses")
        assert billing_analyses_resp.status_code == 200
        billing_analyses = [
            PRAnalysisResponse.model_validate(item) for item in billing_analyses_resp.json()
        ]
        assert [a.pr_number for a in billing_analyses] == [42, 47]
        assert all(
            a.citation_telemetry is not None and a.citation_telemetry.hallucination_caught == 0
            for a in billing_analyses
        )

        fulfillment_analyses_resp = await client.get(
            f"/api/repos/{DEMO_FULFILLMENT_REPO_ID}/analyses"
        )
        assert fulfillment_analyses_resp.status_code == 200
        fulfillment_analyses = [
            PRAnalysisResponse.model_validate(item) for item in fulfillment_analyses_resp.json()
        ]
        assert [a.pr_number for a in fulfillment_analyses] == [51]
        assert fulfillment_analyses[0].ai_report is not None
        assert fulfillment_analyses[0].ai_report.overall_risk == "high"
        assert (
            fulfillment_analyses[0].citation_telemetry is not None
            and fulfillment_analyses[0].citation_telemetry.hallucination_caught == 0
        )


async def test_startup_seeding_runs_when_enabled(sqlite_engine: AsyncEngine) -> None:
    """FastAPI lifespan seeds demo data automatically when seed_demo_on_startup=True."""
    settings = Settings(
        environment="test",
        log_level="WARNING",
        database_url="sqlite+aiosqlite:///:memory:",
        seed_demo_on_startup=True,
    )
    app = create_app(settings=settings, db_engine=sqlite_engine)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            resp = await client.get("/api/repos")
            assert resp.status_code == 200
            assert len(resp.json()) == 2
