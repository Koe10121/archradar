"""Unit and integration tests for diff parsing, citation gate, AI retry, and webhooks."""

import hashlib
import hmac
import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.config import Settings
from app.main import create_app
from app.schemas.analysis import (
    BlastRadiusReport,
    BlastRadiusResult,
    ImpactedFlow,
    PRAnalysisResponse,
)
from app.schemas.repo import RepoIndexResponse
from app.services.ai_analyzer import AIAnalyzer, LLMGenerationResult
from app.services.blast_radius import NodeSnapshot
from app.services.citation_validator import validate_report_citations
from app.services.github import (
    parse_unified_diff,
    prioritize_and_truncate_diff,
    verify_github_webhook_signature,
)


class MockLLMProvider:
    """Deterministic mock LLM provider supporting scripted responses."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.last_user_prompt = ""

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BlastRadiusReport],
    ) -> LLMGenerationResult:
        del system_prompt, response_schema
        self.last_user_prompt = user_prompt
        text = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return LLMGenerationResult(
            raw_text=text,
            model_used="gemini-2.5-flash-mock",
            prompt_tokens=1200,
            completion_tokens=300,
        )


def test_parse_unified_diff_and_reject_traversal() -> None:
    """parse_unified_diff extracts paths and symbols and rejects traversal paths."""
    sample_diff = """diff --git a/src/services/auth.ts b/src/services/auth.ts
index 1111111..2222222 100644
--- a/src/services/auth.ts
+++ b/src/services/auth.ts
@@ -1,3 +1,3 @@
-export function verifyToken(token: string): boolean {
+export function verifyToken(token: string, strict: boolean): boolean {
   return Boolean(token);
 }
"""
    parsed = parse_unified_diff(sample_diff)
    assert parsed.changed_files == ["src/services/auth.ts"]
    assert "verifyToken" in parsed.changed_symbols_by_file["src/services/auth.ts"]

    bad_diff = """diff --git a/../../etc/passwd b/../../etc/passwd
--- a/../../etc/passwd
+++ b/../../etc/passwd
@@ -1 +1 @@
-a
+b
"""
    with pytest.raises(ValueError):
        parse_unified_diff(bad_diff)


def test_citation_validator_strips_phantom_files() -> None:
    """Post-LLM citation gate strips unverified paths and promotes valid entry files."""
    report = BlastRadiusReport(
        overall_risk="high",
        confidence=0.92,
        executive_summary="Token signature change breaks webhook verification.",
        breaking_change_detected=True,
        impacted_flows=[
            ImpactedFlow(
                title="Webhook Auth",
                severity="high",
                entry_file="src/phantom/nonexistent.ts",
                affected_files=["src/routes/webhook.ts", "src/phantom/also_fake.ts"],
                explanation="Calls verifyToken with 1 argument.",
                suggested_test="Verify webhook rejects invalid signature.",
            ),
            ImpactedFlow(
                title="Completely Hallucinated Flow",
                severity="low",
                entry_file="src/ghost.ts",
                affected_files=["src/ghost2.ts"],
                explanation="No real files.",
                suggested_test="None.",
            ),
        ],
        doc_drift_alerts=[],
        reviewer_checklist=["Update callers of verifyToken"],
    )

    valid_paths = {"src/services/auth.ts", "src/routes/webhook.ts"}
    sanitized, telemetry = validate_report_citations(report, valid_paths)

    assert telemetry.hallucination_caught == 4
    assert telemetry.valid_cited_paths == 1
    assert len(sanitized.impacted_flows) == 1
    assert sanitized.impacted_flows[0].entry_file == "src/routes/webhook.ts"
    assert sanitized.impacted_flows[0].affected_files == ["src/routes/webhook.ts"]


async def test_analyze_pr_end_to_end_with_retry_and_citation_gate(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
) -> None:
    """POST /api/repos/{id}/analyze-pr retries invalid JSON and persists verified report."""
    (tmp_path / "src" / "services").mkdir(parents=True)
    (tmp_path / "src" / "routes").mkdir(parents=True)
    (tmp_path / "src" / "services" / "auth.ts").write_text(
        "export function verifyToken(token: string): boolean { return Boolean(token); }\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "routes" / "webhook.ts").write_text(
        "import { verifyToken } from '../services/auth';\n"
        "export function handleWebhook(tok: string): boolean { return verifyToken(tok); }\n",
        encoding="utf-8",
    )

    valid_report_json = json.dumps(
        {
            "overall_risk": "high",
            "confidence": 0.9,
            "executive_summary": "Adding required parameter to verifyToken breaks webhook.",
            "breaking_change_detected": True,
            "impacted_flows": [
                {
                    "title": "Webhook verification",
                    "severity": "high",
                    "entry_file": "src/routes/webhook.ts",
                    "affected_files": ["src/services/auth.ts", "src/hallucinated.ts"],
                    "explanation": "handleWebhook calls verifyToken without new parameter.",
                    "suggested_test": "Call handleWebhook with missing strict flag.",
                }
            ],
            "doc_drift_alerts": [],
            "reviewer_checklist": ["Check all callers of verifyToken"],
        }
    )
    mock_llm = MockLLMProvider(responses=["{not valid json", valid_report_json])
    app = create_app(settings=test_settings, db_engine=sqlite_engine, llm_provider=mock_llm)

    raw_diff = (
        "diff --git a/src/services/auth.ts b/src/services/auth.ts\n"
        "--- a/src/services/auth.ts\n"
        "+++ b/src/services/auth.ts\n"
        "@@ -1 +1 @@\n"
        "-export function verifyToken(token: string): boolean { return Boolean(token); }\n"
        "+export function verifyToken(token: string, strict: boolean): boolean "
        "{ return strict && Boolean(token); }\n"
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        idx_resp = await client.post("/api/repos/index", json={"local_path": str(tmp_path)})
        assert idx_resp.status_code == 201
        repo_id = RepoIndexResponse.model_validate(idx_resp.json()).repository_id

        analyze_resp = await client.post(
            f"/api/repos/{repo_id}/analyze-pr",
            json={"raw_diff": raw_diff, "pr_title": "Require strict token validation"},
        )
        assert analyze_resp.status_code == 201
        analysis = PRAnalysisResponse.model_validate(analyze_resp.json())

        assert mock_llm.calls == 2
        assert analysis.blast_radius.direct == ["src/services/auth.ts"]
        assert analysis.blast_radius.hop_1 == ["src/routes/webhook.ts"]
        assert analysis.ai_report is not None
        assert analysis.ai_report.impacted_flows[0].affected_files == ["src/services/auth.ts"]
        assert analysis.citation_telemetry is not None
        assert analysis.citation_telemetry.hallucination_caught == 1
        assert analysis.citation_telemetry.stripped_paths == ["src/hallucinated.ts"]

        get_resp = await client.get(f"/api/analyses/{analysis.id}")
        assert get_resp.status_code == 200
        fetched = PRAnalysisResponse.model_validate(get_resp.json())
        assert fetched.id == analysis.id


async def test_github_webhook_hmac_verification(sqlite_engine: AsyncEngine) -> None:
    """Webhook endpoint enforces strict HMAC-SHA256 verification before parsing JSON."""
    secret = "super-secret-webhook-key"
    settings = Settings(
        environment="test",
        log_level="WARNING",
        database_url="sqlite+aiosqlite:///:memory:",
        github_webhook_secret=secret,
    )
    app = create_app(settings=settings, db_engine=sqlite_engine)
    payload_bytes = json.dumps(
        {
            "action": "opened",
            "repository": {"full_name": "acme/archradar"},
            "pull_request": {"number": 42},
        }
    ).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    valid_sig = f"sha256={digest}"

    assert verify_github_webhook_signature(payload_bytes, valid_sig, secret) is True
    assert verify_github_webhook_signature(payload_bytes, "sha256=deadbeef", secret) is False

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        bad_resp = await client.post(
            "/api/webhooks/github",
            content=b"{malformed-json",
            headers={"X-Hub-Signature-256": "sha256=invalid", "X-GitHub-Event": "pull_request"},
        )
        assert bad_resp.status_code == 401

        missing_resp = await client.post(
            "/api/webhooks/github",
            content=payload_bytes,
            headers={"X-GitHub-Event": "pull_request"},
        )
        assert missing_resp.status_code == 401

        ok_resp = await client.post(
            "/api/webhooks/github",
            content=payload_bytes,
            headers={"X-Hub-Signature-256": valid_sig, "X-GitHub-Event": "pull_request"},
        )
        assert ok_resp.status_code == 202
        assert ok_resp.json()["pr_number"] == 42


def test_prioritize_diff_preserves_buried_breaking_hunk() -> None:
    """Smart priority truncation promotes buried breaking hunks ahead of noisy comments."""
    noisy_lines = "\n".join(
        f"+// noisy generated comment line {idx:03d}: padding-scale=16px" for idx in range(230)
    )
    large_diff = (
        "diff --git a/src/styles/theme.ts b/src/styles/theme.ts\n"
        "--- a/src/styles/theme.ts\n"
        "+++ b/src/styles/theme.ts\n"
        "@@ -1,2 +1,232 @@\n"
        " export const THEME = {\n"
        f"{noisy_lines}\n"
        " };\n"
        "diff --git a/src/lib/crypto.ts b/src/lib/crypto.ts\n"
        "--- a/src/lib/crypto.ts\n"
        "+++ b/src/lib/crypto.ts\n"
        "@@ -1,3 +1,3 @@\n"
        "-export function verifyHmacSignature(payload: string, sig: string): boolean {\n"
        "+export function verifyWebhookSignature(payload: string, sig: string): boolean {\n"
        "   return Boolean(payload && sig);\n"
        " }\n"
    )
    assert len(large_diff) > 12_000

    parsed = parse_unified_diff(
        large_diff,
        max_chars=12_000,
        in_degree_by_file={"src/styles/theme.ts": 0, "src/lib/crypto.ts": 2},
    )
    assert len(parsed.truncated_diff) <= 12_000
    assert "src/lib/crypto.ts" in parsed.truncated_diff
    assert "verifyWebhookSignature" in parsed.truncated_diff
    assert parsed.truncated_diff.index("src/lib/crypto.ts") < parsed.truncated_diff.index(
        "src/styles/theme.ts"
    )


def test_prioritize_diff_prefers_high_in_degree_and_sensitive_boundaries() -> None:
    """Priority truncation ranks high in_degree hubs and sensitive boundaries before leaf files."""
    short_diff = (
        "diff --git a/src/leaf.ts b/src/leaf.ts\n--- a/src/leaf.ts\n+++ b/src/leaf.ts\n"
        "@@ -1 +1 @@\n-const x = 1;\n+const x = 2;\n"
    )
    assert prioritize_and_truncate_diff(short_diff, max_chars=12_000) == short_diff

    leaf_padding = "\n".join(f"+const item{i} = {i};" for i in range(40))
    multi_diff = (
        "diff --git a/src/ui/widget.ts b/src/ui/widget.ts\n"
        "--- a/src/ui/widget.ts\n"
        "+++ b/src/ui/widget.ts\n"
        "@@ -1,1 +1,41 @@\n"
        " const base = 0;\n"
        f"{leaf_padding}\n"
        "diff --git a/src/middleware/auth.ts b/src/middleware/auth.ts\n"
        "--- a/src/middleware/auth.ts\n"
        "+++ b/src/middleware/auth.ts\n"
        "@@ -1,1 +1,1 @@\n"
        "-export function requireAuth(req: Request): boolean { return true; }\n"
        "+export function requireAuth(req: Request, role: string): boolean {\n"
        "+  return Boolean(role);\n"
        "+}\n"
    )
    bounded = prioritize_and_truncate_diff(
        multi_diff,
        max_chars=450,
        in_degree_by_file={"src/ui/widget.ts": 0, "src/middleware/auth.ts": 4},
    )
    assert len(bounded) <= 450
    assert "src/middleware/auth.ts" in bounded
    assert "requireAuth(req: Request, role: string)" in bounded


async def test_ai_analyzer_uses_priority_diff_with_raw_diff() -> None:
    """AIAnalyzer.analyze prioritizes raw_diff hunks using graph centrality before prompting."""
    valid_report_json = json.dumps(
        {
            "overall_risk": "high",
            "confidence": 0.92,
            "executive_summary": "verifyWebhookSignature rename breaks stripe webhook.",
            "breaking_change_detected": True,
            "impacted_flows": [
                {
                    "title": "Webhook Verification",
                    "severity": "high",
                    "entry_file": "src/api/webhooks/stripe.ts",
                    "affected_files": ["src/lib/crypto.ts"],
                    "explanation": "Renamed verifyHmacSignature.",
                    "suggested_test": "Test webhook verification.",
                }
            ],
            "doc_drift_alerts": [],
            "reviewer_checklist": ["Update stripe webhook import"],
        }
    )
    mock_llm = MockLLMProvider(responses=[valid_report_json])
    analyzer = AIAnalyzer(provider=mock_llm)

    noise = "\n".join(f"+// noise {i:03d}: padding token" for i in range(40))
    raw_diff = (
        "diff --git a/src/styles/theme.ts b/src/styles/theme.ts\n"
        "--- a/src/styles/theme.ts\n"
        "+++ b/src/styles/theme.ts\n"
        "@@ -1,1 +1,41 @@\n"
        " export const THEME = {};\n"
        f"{noise}\n"
        "diff --git a/src/lib/crypto.ts b/src/lib/crypto.ts\n"
        "--- a/src/lib/crypto.ts\n"
        "+++ b/src/lib/crypto.ts\n"
        "@@ -1,1 +1,1 @@\n"
        "-export function verifyHmacSignature(): boolean { return true; }\n"
        "+export function verifyWebhookSignature(): boolean { return true; }\n"
    )
    nodes = [
        NodeSnapshot("src/styles/theme.ts", "typescript", "src/styles", 50, 0, 0, []),
        NodeSnapshot("src/lib/crypto.ts", "typescript", "src/lib", 20, 3, 0, []),
        NodeSnapshot("src/api/webhooks/stripe.ts", "typescript", "src/api", 40, 0, 1, []),
    ]
    blast = BlastRadiusResult(
        direct=["src/styles/theme.ts", "src/lib/crypto.ts"],
        hop_1=["src/api/webhooks/stripe.ts"],
        hop_2=[],
        hop_3=[],
        score=70,
        deterministic_risk="high",
        max_in_degree=3,
        sensitive_boundaries_touched=["webhooks"],
        symbol_matched_files=["src/api/webhooks/stripe.ts"],
        impacted_edges=[],
    )

    await analyzer.analyze(
        pr_title="Massive theme update + crypto rename",
        pr_description="",
        truncated_diff="ignored prefix",
        nodes=nodes,
        blast_radius=blast,
        raw_diff=raw_diff,
        max_diff_chars=500,
    )
    assert "verifyWebhookSignature" in mock_llm.last_user_prompt
