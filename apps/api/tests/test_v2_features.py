"""Tests for Historical Snapshot Diff API and Telemetry & Cost Analytics API."""

import json
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.db.session import create_session_factory
from app.main import create_app
from app.schemas.analysis import BlastRadiusReport
from app.schemas.repo import RepoIndexResponse, SnapshotDiffResponse
from app.schemas.telemetry import TelemetrySummaryResponse
from app.services.ai_analyzer import LLMGenerationResult
from app.services.demo_seeder import (
    DEMO_BILLING_REPO_ID,
    DEMO_BILLING_SNAPSHOT_ID,
    DEMO_BILLING_V1_SNAPSHOT_ID,
    seed_demo_data,
)


class _HallucinatingMockLLM:
    def __init__(self, raw_text: str) -> None:
        self._raw_text = raw_text

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BlastRadiusReport],
    ) -> LLMGenerationResult:
        del system_prompt, user_prompt, response_schema
        return LLMGenerationResult(
            raw_text=self._raw_text,
            model_used="gemini-2.5-flash-eval",
            prompt_tokens=1500,
            completion_tokens=400,
        )


async def test_snapshot_diff_endpoint_computes_added_removed_and_centrality_deltas(
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """GET /api/repos/{id}/snapshots/diff returns added/removed files, edges, and degree deltas."""
    session_factory = create_session_factory(sqlite_engine)
    async with session_factory() as session:
        await seed_demo_data(session)

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        diff_resp = await client.get(
            f"/api/repos/{DEMO_BILLING_REPO_ID}/snapshots/diff",
            params={
                "from_snapshot_id": str(DEMO_BILLING_V1_SNAPSHOT_ID),
                "to_snapshot_id": str(DEMO_BILLING_SNAPSHOT_ID),
            },
        )
        assert diff_resp.status_code == 200
        diff = SnapshotDiffResponse.model_validate(diff_resp.json())

        assert diff.file_count_delta == 3
        assert diff.edge_count_delta == 5
        assert diff.added_files == [
            "src/lib/crypto.ts",
            "src/middleware/rate_limit.ts",
            "src/services/audit.ts",
            "src/workers/invoiceWorker.ts",
        ]
        assert diff.removed_files == ["src/lib/legacyBillingClient.ts"]

        added_pairs = {(e.source_path, e.target_path) for e in diff.added_edges}
        removed_pairs = {(e.source_path, e.target_path) for e in diff.removed_edges}
        assert ("src/api/webhooks/stripe.ts", "src/lib/crypto.ts") in added_pairs
        assert ("src/workers/invoiceWorker.ts", "src/services/billing.ts") in added_pairs
        assert ("src/services/billing.ts", "src/lib/legacyBillingClient.ts") in removed_pairs
        assert ("src/ui/BillingSummary.tsx", "src/middleware/auth.ts") in removed_pairs

        deltas_by_path = {d.path: d for d in diff.centrality_deltas}
        assert deltas_by_path["src/lib/token.ts"].in_degree_delta == 1
        assert deltas_by_path["src/middleware/auth.ts"].in_degree_delta == -1
        assert deltas_by_path["src/api/routes/checkout.ts"].in_degree_delta == 2
        assert deltas_by_path["src/services/audit.ts"].status == "added"
        assert deltas_by_path["src/lib/legacyBillingClient.ts"].status == "removed"

        missing_resp = await client.get(
            f"/api/repos/{DEMO_BILLING_REPO_ID}/snapshots/diff",
            params={
                "from_snapshot_id": str(uuid4()),
                "to_snapshot_id": str(DEMO_BILLING_SNAPSHOT_ID),
            },
        )
        assert missing_resp.status_code == 404


async def test_telemetry_summary_aggregates_seeded_and_intercepted_analyses(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """GET /api/telemetry/summary returns empty zeros, seeded metrics, and gate intercepts."""
    app_empty = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport_empty = httpx.ASGITransport(app=app_empty)
    async with httpx.AsyncClient(
        transport=transport_empty, base_url="http://testserver"
    ) as client:
        empty_resp = await client.get("/api/telemetry/summary")
        assert empty_resp.status_code == 200
        empty_summary = TelemetrySummaryResponse.model_validate(empty_resp.json())
        assert empty_summary.total_analyses == 0
        assert empty_summary.projected_cost_per_1000_prs_usd == 0.0

    session_factory = create_session_factory(sqlite_engine)
    async with session_factory() as session:
        await seed_demo_data(session)

    async with httpx.AsyncClient(
        transport=transport_empty, base_url="http://testserver"
    ) as client:
        seeded_resp = await client.get("/api/telemetry/summary")
        assert seeded_resp.status_code == 200
        seeded = TelemetrySummaryResponse.model_validate(seeded_resp.json())
        assert seeded.total_analyses == 3
        assert seeded.ai_enabled_analyses == 3
        assert seeded.risk_counts.critical == 1
        assert seeded.risk_counts.high == 1
        assert seeded.risk_counts.low == 1
        assert seeded.risk_counts.medium == 0
        assert seeded.median_latency_ms == 1180.0
        assert seeded.p95_latency_ms == 1420.0
        assert seeded.citation_gate_intercepts == 0
        assert seeded.valid_cited_paths == 12
        assert seeded.projected_cost_per_1000_prs_usd > 0

    # Also test persisted citation-gate intercept aggregation after a live/mocked analysis
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth.ts").write_text("export function auth(): boolean { return true; }\n")
    hallucinated_payload = json.dumps(
        {
            "overall_risk": "medium",
            "confidence": 0.85,
            "executive_summary": "Modified auth module.",
            "breaking_change_detected": True,
            "impacted_flows": [
                {
                    "title": "Auth flow",
                    "severity": "medium",
                    "entry_file": "src/auth.ts",
                    "affected_files": ["src/auth.ts", "src/phantom/ghost.ts"],
                    "explanation": "Auth change.",
                    "suggested_test": "Test auth.",
                }
            ],
            "doc_drift_alerts": [],
            "reviewer_checklist": ["Check auth"],
        }
    )
    app_with_llm = create_app(
        settings=test_settings,
        db_engine=sqlite_engine,
        llm_provider=_HallucinatingMockLLM(hallucinated_payload),
    )
    transport_llm = httpx.ASGITransport(app=app_with_llm)
    async with httpx.AsyncClient(transport=transport_llm, base_url="http://testserver") as client:
        idx_resp = await client.post("/api/repos/index", json={"local_path": str(tmp_path)})
        assert idx_resp.status_code == 201
        repo_id = RepoIndexResponse.model_validate(idx_resp.json()).repository_id

        raw_diff = (
            "diff --git a/src/auth.ts b/src/auth.ts\n"
            "--- a/src/auth.ts\n"
            "+++ b/src/auth.ts\n"
            "@@ -1 +1 @@\n"
            "-export function auth(): boolean { return true; }\n"
            "+export function auth(strict: boolean): boolean { return strict; }\n"
        )
        analyze_resp = await client.post(
            f"/api/repos/{repo_id}/analyze-pr",
            json={"raw_diff": raw_diff, "pr_title": "Add strict flag", "run_ai": True},
        )
        assert analyze_resp.status_code == 201

        after_resp = await client.get("/api/telemetry/summary")
        assert after_resp.status_code == 200
        after = TelemetrySummaryResponse.model_validate(after_resp.json())
        assert after.total_analyses == 4
        assert after.citation_gate_intercepts == 1
        assert after.models[0].model == "gemini-2.5-flash"
