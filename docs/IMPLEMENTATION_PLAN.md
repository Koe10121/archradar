# Implementation Plan & Phased Roadmap — ArchRadar

Work through these phases sequentially. Check off items only after running verification tests.

---

## Phase 0: Workspace & Infrastructure Bootstrap
- [ ] Initialize monorepo structure (`apps/web`, `apps/api`, `evals`, `docs`).
- [ ] Create `docker-compose.yml` with PostgreSQL 16 and Redis.
- [ ] Create `.env.example` and `.gitignore` (ensuring `.env`, `__pycache__`, `node_modules`, `.next` are ignored).
- [ ] Scaffold FastAPI app in `apps/api` with `/api/health`, SQLAlchemy async engine, and Alembic migrations.
- [ ] Scaffold Next.js 15 + Tailwind + shadcn/ui app in `apps/web` with TypeScript strict mode.
- [ ] Verify both services start cleanly and `apps/web` can reach `apps/api/health`.

## Phase 1: Deterministic AST Engine (Tree-sitter)
- [ ] Implement `LanguageAdapter` interface in `apps/api/app/parser/base.py`.
- [ ] Implement `TypeScriptAdapter` (handles ES imports, `require()`, re-exports, exported functions/classes/types, relative paths, and `@/` aliases).
- [ ] Implement `PythonAdapter` (handles `import`, `from ... import`, relative dots `.`/`..`, `__init__.py` resolution, top-level `def`/`class`).
- [ ] Build `RepoIndexer` service: fetches repository tree (via GitHub Archive/API or shallow clone in temp dir), parses files, resolves edges, computes `in_degree`/`out_degree`, saves snapshot to PostgreSQL.
- [ ] Write unit tests in `apps/api/tests/test_parser.py` covering barrel files, circular imports, aliases, and syntax errors.

## Phase 2: Blast-Radius Engine & Grounded AI Pipeline
- [ ] Implement `BlastRadiusCalculator` (reverse BFS up to depth 3 + symbol-level edge matching + deterministic risk score).
- [ ] Implement GitHub PR diff fetcher (`apps/api/app/services/github.py`) + raw diff parser (`unidiff`).
- [ ] Define `BlastRadiusReport` Pydantic schemas (`apps/api/app/schemas/analysis.py`).
- [ ] Build LLM analyzer (`apps/api/app/services/ai_analyzer.py`) using structured JSON outputs, token tracking, latency measurement, and cost calculation.
- [ ] Build Post-LLM Citation Validator that verifies every cited file path exists in the snapshot graph.
- [ ] Implement `POST /api/webhooks/github` with strict HMAC-SHA256 signature validation.
- [ ] Write unit + mocked integration tests for blast-radius BFS and citation validation.

## Phase 3: Interactive Living Architecture UI (Next.js + React Flow)
- [ ] Build Graph Canvas component using `@xyflow/react` + Dagre/ELK automatic layout.
- [ ] Create custom File Node component showing language badge, folder color coding, LOC, and centrality badge.
- [ ] Implement Node Inspector side drawer (exported symbols, upstream/downstream clickable links).
- [ ] Implement **PR Blast-Radius Overlay Mode**:
  - Highlight modified (amber), 1-hop (red), 2-hop (soft red), and dim unaffected nodes.
  - Display AI Risk Report panel (severity badge, impacted flows that pan/focus the graph when clicked, doc-drift Markdown patch with copy button, reviewer checklist).
- [ ] Build "Analyze a PR" modal (supports GitHub PR URL or pasting a sample diff) + "Index New Repo" flow with live progress status.

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
