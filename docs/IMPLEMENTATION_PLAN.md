# Implementation Plan & Phased Roadmap — ArchRadar

Work through these phases sequentially. Check off items only after running verification tests.

---

## Phase 0: Workspace & Infrastructure Bootstrap
- [x] Initialize monorepo structure (`apps/web`, `apps/api`, `evals`, `docs`).
- [x] Create `docker-compose.yml` with PostgreSQL 16 and Redis.
- [x] Create `.env.example` and `.gitignore` (ensuring `.env`, `__pycache__`, `node_modules`, `.next` are ignored).
- [x] Scaffold FastAPI app in `apps/api` with `/api/health`, SQLAlchemy async engine, and Alembic migrations.
- [x] Scaffold Next.js 15 + Tailwind + shadcn/ui app in `apps/web` with TypeScript strict mode.
- [x] Verify both services start cleanly and `apps/web` can reach `apps/api/health`.

## Phase 1: Deterministic AST Engine (Tree-sitter)
- [x] Implement `LanguageAdapter` interface in `apps/api/app/parser/base.py`.
- [x] Implement `TypeScriptAdapter` (handles ES imports, `require()`, re-exports, exported functions/classes/types, relative paths, and `@/` aliases).
- [x] Implement `PythonAdapter` (handles `import`, `from ... import`, relative dots `.`/`..`, `__init__.py` resolution, top-level `def`/`class`).
- [x] Build `RepoIndexer` service: fetches repository tree (via GitHub Archive/API or shallow clone in temp dir), parses files, resolves edges, computes `in_degree`/`out_degree`, saves snapshot to PostgreSQL.
- [x] Write unit tests in `apps/api/tests/test_parser.py` covering barrel files, circular imports, aliases, and syntax errors.

## Phase 2: Blast-Radius Engine & Grounded AI Pipeline
- [x] Implement `BlastRadiusCalculator` (reverse BFS up to depth 3 + symbol-level edge matching + deterministic risk score).
- [x] Implement GitHub PR diff fetcher (`apps/api/app/services/github.py`) + raw diff parser (`unidiff`).
- [x] Define `BlastRadiusReport` Pydantic schemas (`apps/api/app/schemas/analysis.py`).
- [x] Build LLM analyzer (`apps/api/app/services/ai_analyzer.py`) using structured JSON outputs, token tracking, latency measurement, and cost calculation.
- [x] Build Post-LLM Citation Validator that verifies every cited file path exists in the snapshot graph.
- [x] Implement `POST /api/webhooks/github` with strict HMAC-SHA256 signature validation.
- [x] Write unit + mocked integration tests for blast-radius BFS and citation validation.

## Phase 3: Interactive Living Architecture UI (Next.js + React Flow)
- [x] Build Graph Canvas component using `@xyflow/react` + Dagre/ELK automatic layout.
- [x] Create custom File Node component showing language badge, folder color coding, LOC, and centrality badge.
- [x] Implement Node Inspector side drawer (exported symbols, upstream/downstream clickable links).
- [x] Implement **PR Blast-Radius Overlay Mode**:
  - Highlight modified (amber), 1-hop (red), 2-hop (soft red), and dim unaffected nodes.
  - Display AI Risk Report panel (severity badge, impacted flows that pan/focus the graph when clicked, doc-drift Markdown patch with copy button, reviewer checklist).
- [x] Build "Analyze a PR" modal (supports GitHub PR URL or pasting a sample diff) + "Index New Repo" flow with live progress status.

## Phase 4: Evaluation Suite & Zero-Friction Demo Mode
- [x] Seed 2 rich pre-indexed demo repositories + 3 realistic pre-computed PR scenarios (e.g., Safe Refactor, Subtle Webhook Breakage, High-Risk Auth Middleware Change).
- [x] Build the 30-case benchmark suite in `evals/` (see `docs/EVALUATION_SUITE.md`).
- [x] Run benchmark, record precision/recall/citation-accuracy/latency/cost metrics, and save `evals/results/latest_report.md`.

## Phase 5: Portfolio Polish & Deployment
- [x] Deploy frontend to **Vercel Production** (`https://archradar.vercel.app`) + GitHub Actions CI (`.github/workflows/ci.yml` on `Koe10121/archradar`); backend + Postgres deployment blueprints ready (`render.yaml`, `apps/api/fly.toml`) for optional live indexing beyond standalone Demo Mode.
- [x] Write a standout root `README.md` featuring:
  - Live production screenshot & 60-second interactive tour right at the top
  - Live demo URL (`https://archradar.vercel.app`) & CI status badge
  - System architecture diagram & 5-language support matrix
  - Real evaluation metrics (35/35) & failure analysis log
  - Cost-per-1,000-PRs breakdown

## Phase 6: V1.1 Accuracy Fix & V2 Local-First Capabilities
- [x] **Smart Priority Diff Truncation (`case_030` -> 30/30):** Upgraded `parse_unified_diff` / `prioritize_and_truncate_diff` (`apps/api/app/services/github.py`) and `AIAnalyzer.prepare_diff_for_prompt` (`apps/api/app/services/ai_analyzer.py`) to prioritize file hunks touching sensitive boundaries, high `in_degree` nodes, and exported signature changes before enforcing the 12,000-char token budget; added unit tests and re-ran benchmark to **30/30 full pass**.
- [x] **Historical Architecture Drift Timeline:** Added `GET /api/repos/{repo_id}/graph?snapshot_id=...`, `GET /api/repos/{repo_id}/snapshots`, and `GET /api/repos/{repo_id}/snapshots/diff` (`apps/api/app/services/snapshot_diff.py` + `apps/api/app/api/routes/repos.py`), extended `demo_seeder.py` and `apps/web/src/lib/demo-data.ts` with `v1 -> v2` snapshots for `acme/saas-billing-platform`, added Zod schemas, and built the Drift Timeline slider/drawer + React Flow canvas diff highlights (`apps/web/src/components/drift-timeline-panel.tsx`).
- [x] **Telemetry & Cost Analytics View:** Persisted `citation_telemetry_json` on `pr_analyses` (with Alembic migration `0002_add_citation_telemetry.py`), added `GET /api/telemetry/summary` (`apps/api/app/api/routes/telemetry.py`), and built the Telemetry modal (`apps/web/src/components/telemetry-modal.tsx`) with synced offline Demo Mode fallback.
- [x] **Go Language Adapter (`tree-sitter-go`):** Added `tree-sitter-go` to `apps/api/pyproject.toml`, implemented `GoAdapter` + `load_go_module_path` (`apps/api/app/parser/go.py`), registered in `ParserRegistry` & `RepoIndexer`, and added parser + indexer tests.

## Phase 7: V2 Completion (PR Comment Bot, Rust & Java, Go Evals, Frontend Tests)
- [x] **GitHub PR Comment Bot Renderer & Dry-Run Preview:** Built `apps/api/app/services/pr_commenter.py`, added `GET /api/analyses/{analysis_id}/pr-comment` (`PRCommentResponse` Pydantic + Zod schemas), wired webhook dry-run comment preview hooks in `apps/api/app/api/routes/webhooks.py`, and added an interactive **PR Comment Preview** + **Copy GitHub Markdown** view inside `apps/web/src/components/blast-radius-panel.tsx` (with synced offline renderer `apps/web/src/lib/pr-comment.ts`).
- [x] **Rust & Java Language Adapters:** Added `tree-sitter-rust` and `tree-sitter-java` to `apps/api/pyproject.toml`, implemented `RustAdapter` (`apps/api/app/parser/rust.py`) and `JavaAdapter` (`apps/api/app/parser/java.py`), registered both in `ParserRegistry`, updated `FileNode` language tags (`RS`, `JAVA`) & `IndexRepoModal`, and added parser + indexer tests.
- [x] **Go Benchmark Fixture & 35-Case Eval Suite:** Added `evals/fixtures/mini_go_service` (`go.mod`, `cmd/server`, `internal/auth`, `internal/billing`, `internal/webhooks`) and 5 golden Go PR cases (`case_031`–`case_035`), updated `evals/run_benchmark.py` and `apps/api/tests/test_evals_suite.py`, and verified **35/35 full pass** with **100.0% Go import precision/recall** (48/48 edges across 4 fixtures).
- [x] **Frontend Automated Test Suite (Vitest):** Added `vitest` (`npm test` -> `vitest run`) to `apps/web/package.json` with unit tests in `apps/web/src/lib/__tests__/` covering Zod schemas, `computeDemoSnapshotDiff`, `computeDemoTelemetrySummary`, and `renderPRCommentMarkdown` (10/10 tests passing).

## Phase 8 — Next-Stage Engineering Upgrade Pack (Completed)
- [x] **Slice 1 — AST Symbol Spans & Monorepo Config Hierarchy:** Added 1-indexed `(start_line, end_line)` spans across all 5 Tree-sitter adapters, AST-span diff-to-symbol mapping (`github.py`), Hard vs. Soft (`co_located_files`) symbol propagation through barrel `re_export` edges (`blast_radius.py`), and nearest-ancestor `tsconfig.json` (`extends`) / `go.mod` resolution (`indexer.py`).
- [x] **Slice 2 — Test Suite Separation & Architecture Health Engine:** Separated downstream `impacted_test_files` + `suggested_test_command` from production risk counts, added `uncovered_files` 2-hop coverage blind-spot detection, and added zero-AI `compute_architecture_health` (`arch_health.py` + `arch-health.ts`) detecting Tarjan SCC circular dependencies, upward layer violations, and coupling hotspots.
- [x] **Slice 3 — Real Automatic Doc-Drift Engine:** Added `SnapshotDocument` ORM entity + Alembic revision `0003_add_snapshot_documents`, Markdown/OpenAPI doc indexing in `RepoIndexer`, symbol/route/env-anchored section retrieval (`doc_retriever.py`), and post-LLM `doc_file` citation verification (`citation_validator.py`).
- [x] **Slice 4 — Reviewer UX Upgrades:** Added **Isolate Subgraph** DAG lens & **Hide Tests** toggle (`architecture-canvas.tsx`), **Architecture Health** sidebar tab (`arch-health-panel.tsx`), **Causal Dependency Chain** breadcrumbs (`node-inspector-drawer.tsx`), **1-Click Recent GitHub PRs** picker (`GET /api/repos/{id}/github-prs` + `analyze-pr-modal.tsx`), and **Saved Analyses History Switcher** (`blast-radius-panel.tsx`).
