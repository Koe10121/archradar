"""Tests for V3 Upgrade Pack: AST spans, symbol pruning, monorepos, arch health, and auto docs."""

import json
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

import app.api.routes.repos as repos_route
from app.core.config import Settings
from app.db.session import create_session_factory
from app.main import create_app
from app.models.entities import SnapshotDocument
from app.parser.registry import ParserRegistry
from app.schemas.analysis import BlastRadiusReport, PRAnalysisResponse
from app.schemas.repo import GitHubPRSummaryDTO, GraphResponse, RepoIndexResponse
from app.services.ai_analyzer import LLMGenerationResult
from app.services.arch_health import compute_architecture_health
from app.services.blast_radius import BlastRadiusCalculator, EdgeSnapshot, NodeSnapshot
from app.services.citation_validator import validate_report_citations
from app.services.github import parse_unified_diff


def test_ast_symbol_spans_extracted_across_all_five_languages() -> None:
    """All 5 Tree-sitter adapters populate 1-indexed (start_line, end_line) symbol spans."""
    registry = ParserRegistry()

    ts_parsed = registry.get_adapter("src/util.ts")
    assert ts_parsed is not None
    ts_res = ts_parsed.parse(
        "src/util.ts",
        "// header\nexport function calc(x: number): number {\n  return x + 1;\n}\n",
    )
    assert ts_res.exports[0].name == "calc"
    assert ts_res.exports[0].start_line == 2
    assert ts_res.exports[0].end_line == 4

    py_adapter = registry.get_adapter("app/svc.py")
    assert py_adapter is not None
    py_res = py_adapter.parse(
        "app/svc.py",
        "import os\n\ndef compute(a: int) -> int:\n    val = a * 2\n    return val\n",
    )
    assert py_res.exports[0].name == "compute"
    assert py_res.exports[0].start_line == 3
    assert py_res.exports[0].end_line == 5

    go_adapter = registry.get_adapter("pkg/auth/verify.go")
    assert go_adapter is not None
    go_res = go_adapter.parse(
        "pkg/auth/verify.go",
        "package auth\n\nfunc Verify(tok string) bool {\n\treturn tok != \"\"\n}\n",
    )
    assert go_res.exports[0].name == "Verify"
    assert go_res.exports[0].start_line == 3
    assert go_res.exports[0].end_line == 5

    rs_adapter = registry.get_adapter("src/lib.rs")
    assert rs_adapter is not None
    rs_res = rs_adapter.parse(
        "src/lib.rs",
        "pub fn hash_token(v: &str) -> usize {\n    v.len()\n}\n",
    )
    assert rs_res.exports[0].name == "hash_token"
    assert rs_res.exports[0].start_line == 1
    assert rs_res.exports[0].end_line == 3

    java_adapter = registry.get_adapter("src/TokenGuard.java")
    assert java_adapter is not None
    java_res = java_adapter.parse(
        "src/TokenGuard.java",
        "public class TokenGuard {\n  public boolean check(String s) {\n    return true;\n  }\n}\n",
    )
    by_name = {e.name: e for e in java_res.exports}
    assert by_name["TokenGuard"].start_line == 1
    assert by_name["TokenGuard"].end_line == 5
    assert by_name["check"].start_line == 2
    assert by_name["check"].end_line == 4


def test_diff_span_mapping_and_co_location_pruning_with_barrel_reexport() -> None:
    """Body edits map via AST spans, prune disjoint named importers, and propagate barrels."""
    exports_map = {
        "src/lib/utils.ts": [
            {
                "name": "formatDate",
                "kind": "function",
                "signature": "export function formatDate(d: string): string",
                "start_line": 1,
                "end_line": 6,
            },
            {
                "name": "hashSecret",
                "kind": "function",
                "signature": "export function hashSecret(s: string): string",
                "start_line": 8,
                "end_line": 14,
            },
        ]
    }
    # Diff edits line 4 inside formatDate body WITHOUT touching the function declaration line!
    raw_diff = (
        "diff --git a/src/lib/utils.ts b/src/lib/utils.ts\n"
        "--- a/src/lib/utils.ts\n"
        "+++ b/src/lib/utils.ts\n"
        "@@ -2,3 +2,3 @@\n"
        "   const trimmed = d.trim();\n"
        "-  return trimmed.slice(0, 10);\n"
        "+  return trimmed.slice(0, 10).toUpperCase();\n"
        " }\n"
    )
    parsed_diff = parse_unified_diff(raw_diff, exports_by_file=exports_map)
    assert parsed_diff.changed_symbols_by_file["src/lib/utils.ts"] == {"formatDate"}
    assert "src/lib/utils.ts" not in parsed_diff.top_level_edited_files

    nodes = [
        NodeSnapshot(
            "src/lib/utils.ts",
            "typescript",
            "src/lib",
            14,
            3,
            0,
            exports_map["src/lib/utils.ts"],
        ),
        NodeSnapshot("src/lib/index.ts", "typescript", "src/lib", 4, 2, 1, []),
        NodeSnapshot("src/ui/InvoiceCard.tsx", "typescript", "src/ui", 40, 0, 1, []),
        NodeSnapshot("src/auth/password.ts", "typescript", "src/auth", 30, 1, 1, []),
        NodeSnapshot("src/routes/login.ts", "typescript", "src/routes", 25, 0, 1, []),
        NodeSnapshot("src/lib/__tests__/utils.test.ts", "typescript", "src/lib", 20, 0, 1, []),
    ]
    edges = [
        # Barrel re-exports both symbols
        EdgeSnapshot(
            "src/lib/index.ts",
            "src/lib/utils.ts",
            "re_export",
            ["formatDate", "hashSecret"],
        ),
        # UI imports formatDate via barrel -> SHOULD be hard impacted at Hop 2 with symbol_match!
        EdgeSnapshot("src/ui/InvoiceCard.tsx", "src/lib/index.ts", "import", ["formatDate"]),
        # Auth imports ONLY hashSecret -> SHOULD be pruned as co_located (not polluting login.ts!)
        EdgeSnapshot("src/auth/password.ts", "src/lib/index.ts", "import", ["hashSecret"]),
        EdgeSnapshot("src/routes/login.ts", "src/auth/password.ts", "import", ["verifyPassword"]),
        # Downstream test file importing formatDate -> separated into impacted_test_files!
        EdgeSnapshot(
            "src/lib/__tests__/utils.test.ts",
            "src/lib/utils.ts",
            "import",
            ["formatDate"],
        ),
    ]

    calc = BlastRadiusCalculator()
    res = calc.calculate(
        nodes=nodes,
        edges=edges,
        changed_files=parsed_diff.changed_files,
        changed_symbols_by_file=parsed_diff.changed_symbols_by_file,
        top_level_edited_files=parsed_diff.top_level_edited_files,
    )

    assert res.direct == ["src/lib/utils.ts"]
    assert res.hop_1 == ["src/lib/index.ts"]
    assert res.hop_2 == ["src/ui/InvoiceCard.tsx"]
    assert "src/auth/password.ts" not in res.hop_2
    assert "src/routes/login.ts" not in res.hop_3
    assert res.co_located_files == ["src/auth/password.ts"]
    assert "src/ui/InvoiceCard.tsx" in res.symbol_matched_files
    assert res.impacted_test_files == ["src/lib/__tests__/utils.test.ts"]
    assert res.suggested_test_command == "npx vitest run src/lib/__tests__/utils.test.ts"


def test_architecture_health_detects_cycles_layer_violations_and_hotspots() -> None:
    """compute_architecture_health finds Tarjan SCC cycles, upward imports, and hotspots."""
    nodes = [
        NodeSnapshot("src/services/order.ts", "typescript", "src/services", 120, 4, 2, []),
        NodeSnapshot("src/services/inventory.ts", "typescript", "src/services", 95, 2, 1, []),
        NodeSnapshot("src/db/order_repo.ts", "typescript", "src/db", 80, 3, 1, []),
        NodeSnapshot("src/routes/orders.ts", "typescript", "src/routes", 60, 1, 1, []),
        NodeSnapshot("src/ui/OrderPage.tsx", "typescript", "src/ui", 70, 0, 1, []),
    ]
    edges = [
        # Cycle: order.ts <-> inventory.ts
        EdgeSnapshot("src/services/order.ts", "src/services/inventory.ts", "import", ["reserve"]),
        EdgeSnapshot("src/services/inventory.ts", "src/services/order.ts", "import", ["OrderDTO"]),
        # Layer violation: db imports routes!
        EdgeSnapshot("src/db/order_repo.ts", "src/routes/orders.ts", "import", ["OrderFilter"]),
        # Normal downward edges feeding order.ts fan-in
        EdgeSnapshot("src/routes/orders.ts", "src/services/order.ts", "import", ["createOrder"]),
        EdgeSnapshot("src/ui/OrderPage.tsx", "src/services/order.ts", "import", ["OrderSummary"]),
    ]

    health = compute_architecture_health(nodes, edges)
    assert health.cycle_count == 1
    assert health.cycles[0].cycle_paths == [
        "src/services/inventory.ts",
        "src/services/order.ts",
        "src/services/inventory.ts",
    ]
    assert health.layer_violation_count == 1
    assert health.layer_violations[0].source_layer == "data"
    assert health.layer_violations[0].target_layer == "presentation"
    assert any(h.path == "src/services/order.ts" for h in health.hotspots)
    assert health.health_score < 100


class _DocInspectingMockLLM:
    def __init__(self) -> None:
        self.last_user_prompt = ""

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BlastRadiusReport],
    ) -> LLMGenerationResult:
        del system_prompt, response_schema
        self.last_user_prompt = user_prompt
        payload = {
            "overall_risk": "high",
            "confidence": 0.92,
            "executive_summary": "Updated token signature and undocumented env var.",
            "breaking_change_detected": True,
            "impacted_flows": [
                {
                    "title": "Web Auth Flow",
                    "severity": "high",
                    "entry_file": "apps/web/src/components/Guard.tsx",
                    "affected_files": ["apps/web/src/lib/auth.ts"],
                    "explanation": "Guard depends on verifySession via @/* alias.",
                    "suggested_test": "Run Guard test.",
                }
            ],
            "doc_drift_alerts": [
                {
                    "doc_file": "README.md",
                    "section": "Environment Variables",
                    "reason": "SESSION_AUDIENCE added.",
                    "suggested_markdown_patch": "+ - `SESSION_AUDIENCE`",
                },
                {
                    "doc_file": "docs/NON_EXISTENT_PHANTOM.md",
                    "section": "Fake",
                    "reason": "Hallucinated doc path.",
                    "suggested_markdown_patch": "+ fake",
                },
            ],
            "reviewer_checklist": ["Update README.md"],
        }
        return LLMGenerationResult(
            raw_text=json.dumps(payload),
            model_used="mock-flash",
            prompt_tokens=800,
            completion_tokens=220,
        )


async def test_monorepo_tsconfig_auto_doc_drift_and_github_prs_endpoint(
    tmp_path: Path,
    sqlite_engine: AsyncEngine,
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Monorepo nested tsconfig, auto SnapshotDocument retrieval, doc gate, and GitHub PR list."""
    # Create a nested monorepo: tsconfig.base.json + apps/web/tsconfig.json (extends base)
    (tmp_path / "tsconfig.base.json").write_text(
        json.dumps({"compilerOptions": {"strict": True}}),
        encoding="utf-8",
    )
    web_dir = tmp_path / "apps" / "web"
    (web_dir / "src" / "lib").mkdir(parents=True)
    (web_dir / "src" / "components").mkdir(parents=True)
    (web_dir / "tsconfig.json").write_text(
        json.dumps(
            {
                "extends": "../../tsconfig.base.json",
                "compilerOptions": {"paths": {"@/*": ["./src/*"]}},
            }
        ),
        encoding="utf-8",
    )
    (web_dir / "src" / "lib" / "auth.ts").write_text(
        "export function verifySession(tok: string): boolean {\n  return tok.length > 0;\n}\n",
        encoding="utf-8",
    )
    (web_dir / "src" / "components" / "Guard.tsx").write_text(
        'import { verifySession } from "@/lib/auth";\n'
        "export function Guard(): boolean {\n  return verifySession('x');\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "# Monorepo App\n\n## Environment Variables\n- `JWT_SECRET` — Used by `verifySession`.\n",
        encoding="utf-8",
    )

    mock_llm = _DocInspectingMockLLM()
    app = create_app(settings=test_settings, db_engine=sqlite_engine, llm_provider=mock_llm)

    async def _fake_gh_prs(
        owner: str, repo: str, *, github_token: str = "", limit: int = 8
    ) -> list[dict[str, object]]:
        del github_token, limit
        return [
            {
                "number": 19,
                "title": f"Refactor auth in {owner}/{repo}",
                "state": "open",
                "author": "octocat",
                "html_url": f"https://github.com/{owner}/{repo}/pull/19",
                "updated_at": "2026-11-27T06:00:00Z",
                "draft": False,
            }
        ]

    monkeypatch.setattr(repos_route, "fetch_github_repo_prs", _fake_gh_prs)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        idx_resp = await client.post(
            "/api/repos/index",
            json={
                "local_path": str(tmp_path),
                "repo_url": "https://github.com/acme/monorepo-app",
            },
        )
        assert idx_resp.status_code == 201
        indexed = RepoIndexResponse.model_validate(idx_resp.json())
        assert indexed.edge_count == 1

        # Verify SnapshotDocument was persisted
        session_factory = create_session_factory(sqlite_engine)
        async with session_factory() as session:
            docs = (
                await session.execute(
                    select(SnapshotDocument).where(
                        SnapshotDocument.snapshot_id == indexed.snapshot_id
                    )
                )
            ).scalars().all()
            assert [d.path for d in docs] == ["README.md"]

        # Verify GraphResponse includes arch_health and symbol line spans
        graph_resp = await client.get(f"/api/repos/{indexed.repository_id}/graph")
        assert graph_resp.status_code == 200
        graph = GraphResponse.model_validate(graph_resp.json())
        assert graph.arch_health is not None
        assert graph.arch_health.cycle_count == 0
        auth_node = next(n for n in graph.nodes if n.path == "apps/web/src/lib/auth.ts")
        assert auth_node.exports[0].start_line == 1
        assert auth_node.exports[0].end_line == 3

        # Verify 1-click GitHub PR list endpoint
        prs_resp = await client.get(f"/api/repos/{indexed.repository_id}/github-prs")
        assert prs_resp.status_code == 200
        prs = [GitHubPRSummaryDTO.model_validate(item) for item in prs_resp.json()]
        assert len(prs) == 1
        assert prs[0].number == 19

        # Analyze PR without doc_context -> auto-injects README.md & strips phantom doc
        raw_diff = (
            "diff --git a/apps/web/src/lib/auth.ts b/apps/web/src/lib/auth.ts\n"
            "--- a/apps/web/src/lib/auth.ts\n"
            "+++ b/apps/web/src/lib/auth.ts\n"
            "@@ -1,3 +1,3 @@\n"
            " export function verifySession(tok: string): boolean {\n"
            "-  return tok.length > 0;\n"
            "+  return tok.length > 0 && Boolean(process.env.SESSION_AUDIENCE);\n"
            " }\n"
        )
        analyze_resp = await client.post(
            f"/api/repos/{indexed.repository_id}/analyze-pr",
            json={"raw_diff": raw_diff, "pr_title": "Require SESSION_AUDIENCE", "run_ai": True},
        )
        assert analyze_resp.status_code == 201
        analysis = PRAnalysisResponse.model_validate(analyze_resp.json())
        assert analysis.blast_radius.hop_1 == ["apps/web/src/components/Guard.tsx"]
        assert analysis.blast_radius.symbol_matched_files == ["apps/web/src/components/Guard.tsx"]
        assert "apps/web/src/lib/auth.ts" in analysis.blast_radius.uncovered_files
        assert "README.md" in mock_llm.last_user_prompt
        assert "JWT_SECRET" in mock_llm.last_user_prompt
        assert analysis.ai_report is not None
        assert [a.doc_file for a in analysis.ai_report.doc_drift_alerts] == ["README.md"]
        assert analysis.citation_telemetry is not None
        assert "docs/NON_EXISTENT_PHANTOM.md" in analysis.citation_telemetry.stripped_paths


def test_citation_validator_preserves_doc_alerts_when_valid_doc_paths_omitted() -> None:
    """Backward-compatibility: when valid_doc_paths is None, doc_drift_alerts remain intact."""
    report = BlastRadiusReport.model_validate(
        {
            "overall_risk": "medium",
            "confidence": 0.85,
            "executive_summary": "Summary",
            "breaking_change_detected": False,
            "impacted_flows": [],
            "doc_drift_alerts": [
                {
                    "doc_file": "README.md",
                    "section": "Config",
                    "reason": "Drift",
                    "suggested_markdown_patch": "+ VAR",
                }
            ],
            "reviewer_checklist": [],
        }
    )
    sanitized, telemetry = validate_report_citations(report, {"src/a.ts"})
    assert len(sanitized.doc_drift_alerts) == 1
    assert telemetry.hallucination_caught == 0
