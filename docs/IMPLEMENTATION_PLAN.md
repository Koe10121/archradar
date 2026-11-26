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
- [ ] Seed 2 rich pre-indexed demo repositories + 3 realistic pre-computed PR scenarios (e.g., Safe Refactor, Subtle Webhook Breakage, High-Risk Auth Middleware Change).
- [ ] Build the 30-case benchmark suite in `evals/` (see `docs/EVALUATION_SUITE.md`).
- [ ] Run benchmark, record precision/recall/citation-accuracy/latency/cost metrics, and save `evals/results/latest_report.md`.

## Phase 5: Portfolio Polish & Deployment
- [ ] Deploy frontend (Vercel) + backend & Postgres (Render / Railway / Fly.io).
- [ ] Write a standout root `README.md` featuring:
  - 60-second demo GIF/video right at the top
  - Live demo URL
  - System architecture diagram
  - Real evaluation metrics & failure analysis log
  - Cost-per-1,000-PRs breakdown
