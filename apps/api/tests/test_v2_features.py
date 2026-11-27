"""Tests for Historical Snapshot Diff API, Telemetry Analytics, and PR Comment Bot."""

import hashlib
import hmac
import json
import ssl
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import httpx
import pytest
from google.genai import errors as genai_errors
from sqlalchemy.ext.asyncio import AsyncEngine

import app.api.routes.analyses as analyses_route
import app.services.ai_analyzer as ai_analyzer_module
from app.core.config import Settings
from app.core.rate_limit import RateLimiter
from app.db.session import create_session_factory, sanitize_asyncpg_url
from app.main import create_app
from app.schemas.analysis import (
    BlastRadiusReport,
    BlastRadiusResult,
    ImpactedEdgeDetail,
    PRAnalysisResponse,
    PRCommentResponse,
)
from app.schemas.repo import RepoIndexResponse, SnapshotDiffResponse
from app.schemas.telemetry import TelemetrySummaryResponse
from app.services.ai_analyzer import (
    GeminiLLMProvider,
    GeminiProviderError,
    LLMGenerationResult,
    sanitize_provider_error,
    select_candidate_flash_models,
)
from app.services.demo_seeder import (
    DEMO_BILLING_REPO_ID,
    DEMO_BILLING_SNAPSHOT_ID,
    DEMO_BILLING_V1_SNAPSHOT_ID,
    seed_demo_data,
)
from app.services.pr_commenter import render_pr_comment


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


def test_render_pr_comment_deterministic_only_and_raw_patch() -> None:
    """render_pr_comment handles deterministic-only (ai_report=None) and Mermaid subgraphs."""
    analysis = PRAnalysisResponse(
        id=uuid4(),
        repository_id=uuid4(),
        snapshot_id=uuid4(),
        pr_number=77,
        pr_title="Harden token audience check",
        changed_files=["src/lib/token.ts"],
        blast_radius=BlastRadiusResult(
            direct=["src/lib/token.ts"],
            hop_1=["src/middleware/auth.ts"],
            hop_2=["src/routes/checkout.ts"],
            hop_3=[],
            score=62,
            deterministic_risk="high",
            max_in_degree=2,
            sensitive_boundaries_touched=["auth", "middleware"],
            symbol_matched_files=["src/middleware/auth.ts"],
            impacted_edges=[
                ImpactedEdgeDetail(
                    source="src/middleware/auth.ts",
                    target="src/lib/token.ts",
                    edge_type="import",
                    imported_symbols=["verifyToken"],
                    symbol_match=True,
                )
            ],
        ),
        ai_report=None,
        citation_telemetry=None,
        model_used=None,
        prompt_tokens=0,
        completion_tokens=0,
        estimated_cost_usd=0.0,
        latency_ms=12,
        created_at=datetime.now(UTC),
    )

    markdown = render_pr_comment(analysis)
    assert "## ArchRadar Blast-Radius Report" in markdown
    assert "#77 — Harden token audience check" in markdown
    assert "**Risk:** `HIGH`" in markdown
    assert "**Score:** `62/100`" in markdown
    assert "**Breaking:** `YES`" in markdown
    assert "```mermaid" in markdown
    assert "flowchart LR" in markdown
    assert 'N1["src/middleware/auth.ts"]' in markdown
    assert 'N1 -->|"verifyToken"| N0' in markdown
    assert "`deterministic-only`" in markdown


async def test_pr_comment_endpoint_and_webhook_dry_run_preview(
    sqlite_engine: AsyncEngine,
) -> None:
    """GET /api/analyses/{id}/pr-comment and webhook dry-run return verified Markdown."""
    session_factory = create_session_factory(sqlite_engine)
    async with session_factory() as session:
        await seed_demo_data(session)

    secret = "dry-run-webhook-secret"
    settings = Settings(
        environment="test",
        log_level="WARNING",
        database_url="sqlite+aiosqlite:///:memory:",
        github_webhook_secret=secret,
    )
    app = create_app(settings=settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        analyses_resp = await client.get(f"/api/repos/{DEMO_BILLING_REPO_ID}/analyses")
        assert analyses_resp.status_code == 200
        analyses = analyses_resp.json()
        pr42 = next(item for item in analyses if item["pr_number"] == 42)

        comment_resp = await client.get(f"/api/analyses/{pr42['id']}/pr-comment")
        assert comment_resp.status_code == 200
        comment = PRCommentResponse.model_validate(comment_resp.json())
        assert comment.character_count == len(comment.markdown)
        assert "**Risk:** `CRITICAL`" in comment.markdown
        assert "```mermaid" in comment.markdown
        assert "src/middleware/auth.ts" in comment.markdown
        assert "### Impacted Flows" in comment.markdown
        assert "### Documentation Drift Alerts" in comment.markdown
        assert "### Reviewer Checklist" in comment.markdown

        missing_resp = await client.get(f"/api/analyses/{uuid4()}/pr-comment")
        assert missing_resp.status_code == 404

        # Webhook dry-run on seeded repo/PR returns persisted comment preview without network calls
        webhook_payload = json.dumps(
            {
                "action": "opened",
                "repository": {"full_name": "acme/saas-billing-platform"},
                "pull_request": {"number": 42},
                "dry_run": True,
            }
        ).encode("utf-8")
        digest = hmac.new(secret.encode("utf-8"), webhook_payload, hashlib.sha256).hexdigest()
        wh_resp = await client.post(
            "/api/webhooks/github",
            content=webhook_payload,
            headers={
                "X-Hub-Signature-256": f"sha256={digest}",
                "X-GitHub-Event": "pull_request",
            },
        )
        assert wh_resp.status_code == 202
        wh_data = wh_resp.json()
        assert wh_data["comment_mode"] == "dry_run"
        assert wh_data["comment_posted"] is False
        assert wh_data["comment_character_count"] == comment.character_count
        assert "## ArchRadar Blast-Radius Report" in wh_data["comment_preview"]

        # Unknown repo dry-run falls back cleanly to pending dry-run placeholder
        pending_payload = json.dumps(
            {
                "action": "synchronize",
                "repository": {"full_name": "acme/unindexed-repo"},
                "pull_request": {"number": 9},
            }
        ).encode("utf-8")
        pending_sig = hmac.new(
            secret.encode("utf-8"), pending_payload, hashlib.sha256
        ).hexdigest()
        pending_resp = await client.post(
            "/api/webhooks/github",
            content=pending_payload,
            headers={
                "X-Hub-Signature-256": f"sha256={pending_sig}",
                "X-GitHub-Event": "pull_request",
                "X-ArchRadar-Dry-Run": "true",
            },
        )
        assert pending_resp.status_code == 202
        pending_data = pending_resp.json()
        assert pending_data["comment_posted"] is False
        assert "Dry-Run Pending" in pending_data["comment_preview"]


def test_sanitize_asyncpg_url_strips_libpq_ssl_params() -> None:
    """Neon/libpq sslmode & channel_binding params convert cleanly for asyncpg."""
    clean_url, connect_args = sanitize_asyncpg_url(
        "postgresql+asyncpg://user:pass@ep-cool-pooler.us-east-1.aws.neon.tech/neondb"
        "?sslmode=require&channel_binding=require&application_name=archradar"
    )
    assert clean_url == (
        "postgresql+asyncpg://user:pass@ep-cool-pooler.us-east-1.aws.neon.tech/neondb"
        "?application_name=archradar"
    )
    assert isinstance(connect_args["ssl"], ssl.SSLContext)
    assert connect_args["statement_cache_size"] == 0

    disabled_url, disabled_args = sanitize_asyncpg_url(
        "postgresql+asyncpg://user:pass@localhost:5432/db?sslmode=disable"
    )
    assert disabled_url == "postgresql+asyncpg://user:pass@localhost:5432/db"
    assert disabled_args["ssl"] is False


async def test_cloud_production_blocks_local_path_and_lazy_bootstraps(
    tmp_path: Path,
) -> None:
    """Production mode rejects local_path indexing (403) and lazily initializes SQLite tables."""
    db_file = tmp_path / "serverless_boot.db"
    settings = Settings(
        environment="production",
        log_level="WARNING",
        database_url=f"sqlite+aiosqlite:///{db_file.as_posix()}",
        auto_init_db=True,
        seed_demo_on_startup=True,
    )
    app = create_app(settings=settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Without running lifespan explicitly, middleware lazily creates tables & seeds demo repos
        health_resp = await client.get("/api/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["database"] == "connected"

        repos_resp = await client.get("/api/repos")
        assert repos_resp.status_code == 200
        assert len(repos_resp.json()) == 2

        local_resp = await client.post(
            "/api/repos/index",
            json={"local_path": str(tmp_path)},
        )
        assert local_resp.status_code == 403


def test_rate_limiter_enforces_quota_and_retry_after() -> None:
    """RateLimiter allows requests up to quota and returns retry_after when exceeded."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.check("1.2.3.4")[0] is True
    assert limiter.check("1.2.3.4")[0] is True
    allowed, retry_after = limiter.check("1.2.3.4")
    assert allowed is False
    assert retry_after >= 1
    assert limiter.check("5.6.7.8")[0] is True


async def test_byok_gemini_key_verify_and_per_request_analyze(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /api/ai/verify-key and X-Gemini-Api-Key header validate cleanly without persistence."""

    async def _fake_verify(api_key: str, model: str) -> tuple[bool, str, str | None]:
        if api_key == "AIzaSyValidTestKey1234567890":
            return True, model, None
        return False, model, "API key expired"

    monkeypatch.setattr(analyses_route, "verify_gemini_key_with_google", _fake_verify)

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("export function run(): void {}\n", encoding="utf-8")

    app = create_app(settings=test_settings, db_engine=sqlite_engine)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        missing_resp = await client.post("/api/ai/verify-key")
        assert missing_resp.status_code == 400

        bad_fmt_resp = await client.post(
            "/api/ai/verify-key",
            headers={"X-Gemini-Api-Key": "has spaces inside"},
        )
        assert bad_fmt_resp.status_code == 400

        invalid_resp = await client.post(
            "/api/ai/verify-key",
            headers={"X-Gemini-Api-Key": "AIzaSyInvalidKey1234567890"},
        )
        assert invalid_resp.status_code == 401
        assert "API key expired" in invalid_resp.json()["detail"]

        valid_resp = await client.post(
            "/api/ai/verify-key",
            headers={"X-Gemini-Api-Key": "AIzaSyValidTestKey1234567890"},
        )
        assert valid_resp.status_code == 200
        assert valid_resp.json()["valid"] is True

        idx_resp = await client.post("/api/repos/index", json={"local_path": str(tmp_path)})
        assert idx_resp.status_code == 201
        repo_id = RepoIndexResponse.model_validate(idx_resp.json()).repository_id

        malformed_analyze = await client.post(
            f"/api/repos/{repo_id}/analyze-pr",
            headers={"X-Gemini-Api-Key": "bad key with spaces"},
            json={
                "raw_diff": (
                    "diff --git a/src/main.ts b/src/main.ts\n"
                    "--- a/src/main.ts\n+++ b/src/main.ts\n"
                    "@@ -1 +1 @@\n-export function run(): void {}\n"
                    "+export function run(x: number): void {}\n"
                ),
                "run_ai": True,
            },
        )
        assert malformed_analyze.status_code == 400


def test_sanitize_provider_error_redacts_api_keys() -> None:
    """sanitize_provider_error strips raw AIza keys and query/header key pairs."""
    raw = (
        "Request failed for https://generativelanguage.googleapis.com?key=AIzaSySecretValue123456 "
        "with x-goog-api-key: my-secret-token\n\tand extra   spaces"
    )
    sanitized = sanitize_provider_error(raw)
    assert "AIzaSySecretValue123456" not in sanitized
    assert "my-secret-token" not in sanitized
    assert "key=[REDACTED]" in sanitized
    assert "x-goog-api-key=[REDACTED]" in sanitized
    assert "  " not in sanitized


def test_select_candidate_flash_models_prioritizes_available_models() -> None:
    """Flash model selector filters incompatible models and ranks newer stable models higher."""
    available = [
        "gemini-embedding-001",
        "imagen-3.0-generate-002",
        "gemini-2.5-flash-tts",
        "gemini-3.8-flash-preview",
        "gemini-3.6-flash",
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
    ]
    selected = select_candidate_flash_models("gemini-2.5-flash", available, limit=3)
    assert selected == ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-2.5-flash-lite"]

    without_preferred = select_candidate_flash_models("gemini-2.5-flash", available[0:6], limit=3)
    assert without_preferred == [
        "gemini-3.6-flash",
        "gemini-2.5-flash-lite",
        "gemini-3.8-flash-preview",
    ]


class _FakeAsyncModels:
    def __init__(self, handler: Any) -> None:
        self._handler = handler

    async def generate_content(self, **kwargs: Any) -> Any:
        return await self._handler(**kwargs)


class _FakeGenAIClient:
    def __init__(self, handler: Any) -> None:
        self.aio = SimpleNamespace(models=_FakeAsyncModels(handler), aclose=None)


async def test_gemini_provider_fallbacks_on_404_429_and_schema_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GeminiLLMProvider falls back cleanly across 404/schema-400/429 without leaking keys."""
    valid_json = json.dumps(
        {
            "overall_risk": "low",
            "confidence": 0.9,
            "executive_summary": "Safe edit.",
            "breaking_change_detected": False,
            "impacted_flows": [],
            "doc_drift_alerts": [],
            "reviewer_checklist": ["Verify tests"],
        }
    )

    async def _mock_fetch_models(
        api_key: str, *, timeout: float = 6.0
    ) -> tuple[int, list[str], str | None]:
        del api_key, timeout
        return 200, ["gemini-3.6-flash", "gemini-2.5-flash-lite"], None

    monkeypatch.setattr(ai_analyzer_module, "fetch_available_gemini_models", _mock_fetch_models)

    # 1. Primary 404 -> discovers available models -> succeeds on fallback model
    seen_models_404: list[str] = []

    async def _handler_404(**kwargs: Any) -> Any:
        model = str(kwargs["model"])
        seen_models_404.append(model)
        if model == "gemini-2.5-flash":
            raise genai_errors.APIError(
                404,
                {"error": {"code": 404, "message": "Model not found", "status": "NOT_FOUND"}},
            )
        return SimpleNamespace(
            text=valid_json,
            usage_metadata=SimpleNamespace(prompt_token_count=120, candidates_token_count=45),
        )

    provider_404 = GeminiLLMProvider(
        api_key="AIzaSyDummyTestKey1234567890", model="gemini-2.5-flash"
    )
    provider_404._client = _FakeGenAIClient(_handler_404)
    res_404 = await provider_404.generate_structured("sys", "usr", BlastRadiusReport)
    assert res_404.model_used == "gemini-3.6-flash"
    assert seen_models_404 == ["gemini-2.5-flash", "gemini-3.6-flash"]

    # 2. Schema 400 -> retries same model without response_schema -> succeeds
    seen_configs: list[bool] = []

    async def _handler_schema_400(**kwargs: Any) -> Any:
        config = kwargs["config"]
        has_schema = getattr(config, "response_schema", None) is not None
        seen_configs.append(has_schema)
        if has_schema:
            raise genai_errors.APIError(
                400,
                {
                    "error": {
                        "code": 400,
                        "message": "Invalid schema minimum field",
                        "status": "INVALID_ARGUMENT",
                    }
                },
            )
        return SimpleNamespace(
            text=valid_json,
            usage_metadata=SimpleNamespace(prompt_token_count=100, candidates_token_count=40),
        )

    provider_schema = GeminiLLMProvider(api_key="AIzaSyDummyTestKey1234567890")
    provider_schema._client = _FakeGenAIClient(_handler_schema_400)
    res_schema = await provider_schema.generate_structured("sys", "usr", BlastRadiusReport)
    assert res_schema.model_used == "gemini-2.5-flash"
    assert seen_configs == [True, False]

    # 3. Exhausted 429 with leaked API key -> raises GeminiProviderError with redacted key
    async def _handler_429(**kwargs: Any) -> Any:
        del kwargs
        raise genai_errors.APIError(
            429,
            {
                "error": {
                    "code": 429,
                    "message": "Quota exceeded for key=AIzaSyLeakySecretKey987654",
                    "status": "RESOURCE_EXHAUSTED",
                }
            },
        )

    provider_429 = GeminiLLMProvider(api_key="AIzaSyLeakySecretKey987654")
    provider_429._client = _FakeGenAIClient(_handler_429)
    with pytest.raises(GeminiProviderError) as exc_info:
        await provider_429.generate_structured("sys", "usr", BlastRadiusReport)
    assert exc_info.value.status_code == 429
    assert "429" in exc_info.value.safe_detail
    assert "AIzaSyLeakySecretKey987654" not in exc_info.value.safe_detail
    assert "[REDACTED" in exc_info.value.safe_detail


class _FailingMockLLM:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BlastRadiusReport],
    ) -> LLMGenerationResult:
        del system_prompt, user_prompt, response_schema
        raise self._exc


async def test_analyze_pr_surfaces_sanitized_gemini_provider_errors(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """POST /api/repos/{id}/analyze-pr maps GeminiProviderError to accurate HTTP status."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.ts").write_text("export function run(): void {}\n", encoding="utf-8")

    raw_diff = (
        "diff --git a/src/main.ts b/src/main.ts\n"
        "--- a/src/main.ts\n+++ b/src/main.ts\n"
        "@@ -1 +1 @@\n-export function run(): void {}\n"
        "+export function run(x: number): void {}\n"
    )

    # 429 quota error surfaced accurately
    app_429 = create_app(
        settings=test_settings,
        db_engine=sqlite_engine,
        llm_provider=_FailingMockLLM(
            GeminiProviderError(
                status_code=429,
                provider_status="RESOURCE_EXHAUSTED",
                model="gemini-2.5-flash",
                safe_detail="Gemini free-tier quota exceeded (HTTP 429).",
            )
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_429), base_url="http://testserver"
    ) as client:
        idx_resp = await client.post("/api/repos/index", json={"local_path": str(tmp_path)})
        assert idx_resp.status_code == 201
        repo_id = RepoIndexResponse.model_validate(idx_resp.json()).repository_id

        resp_429 = await client.post(
            f"/api/repos/{repo_id}/analyze-pr",
            json={"raw_diff": raw_diff, "run_ai": True},
        )
        assert resp_429.status_code == 429
        assert "HTTP 429" in resp_429.json()["detail"]

    # 401 unauthorized key error surfaced accurately
    app_401 = create_app(
        settings=test_settings,
        db_engine=sqlite_engine,
        llm_provider=_FailingMockLLM(
            GeminiProviderError(
                status_code=401,
                provider_status="PERMISSION_DENIED",
                model="gemini-2.5-flash",
                safe_detail="Gemini API key rejected (HTTP 403): API key not valid.",
            )
        ),
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_401), base_url="http://testserver"
    ) as client:
        resp_401 = await client.post(
            f"/api/repos/{repo_id}/analyze-pr",
            json={"raw_diff": raw_diff, "run_ai": True},
        )
        assert resp_401.status_code == 401
        assert "API key rejected" in resp_401.json()["detail"]
