# ArchRadar — Living Architecture Mapper & PR Blast-Radius Radar

You are the lead full-stack and AI systems engineer helping build **ArchRadar**, a production-grade developer tool and portfolio showcase.

## Mission
Build a web platform that connects to a GitHub repository, parses source files deterministically via **Tree-sitter** into an interactive dependency graph (**React Flow**), and analyzes incoming Pull Requests to compute a deterministic **blast radius** plus an AI-generated risk & architecture-drift report.

## Core Design Philosophy (Non-Negotiable)
1. **Deterministic first, LLM second:** Never ask an LLM to guess file imports or call graphs. Tree-sitter builds the ground-truth AST & dependency graph; the LLM only reasons over the **actual git diff + exact impacted subgraph** retrieved from the database.
2. **Strict structured outputs:** Every LLM response must validate against strict JSON schemas (Pydantic on the backend, Zod on the frontend). Reject or retry malformed outputs.
3. **Portfolio-grade engineering:** Clean monorepo boundaries, reproducible Docker setup, real automated tests, and a measurable evaluation suite (`docs/EVALUATION_SUITE.md`).

## Monorepo Layout (Target)
```text
archradar/
├── GEMINI.md                     # Always-on project context (this file)
├── .agents/
│   └── rules/                    # Scoped Antigravity rules
├── docs/
│   ├── PRD.md                    # Product Requirements Document
│   ├── ARCHITECTURE.md           # Technical & System Architecture
│   ├── IMPLEMENTATION_PLAN.md    # Phased build checklist
│   ├── EVALUATION_SUITE.md       # Benchmark & accuracy testing spec
│   └── ANTIGRAVITY_QUICKSTART.md # Setup & kickoff prompts
├── apps/
│   ├── web/                      # Next.js 15 (App Router), TypeScript, Tailwind, React Flow
│   └── api/                      # FastAPI (Python 3.12+), Tree-sitter, SQLAlchemy, Pydantic
├── packages/
│   └── shared-schemas/           # Shared JSON schemas / OpenAPI contract
├── evals/                        # Golden PR fixtures & benchmark runner
└── docker-compose.yml            # PostgreSQL + Redis + API + Web
```

## Key Reference Documents
Read the relevant document before starting any major feature:
- Product scope & user stories: `docs/PRD.md`
- System architecture, DB schema, API contracts: `docs/ARCHITECTURE.md`
- Current phase & checklist: `docs/IMPLEMENTATION_PLAN.md`
- AI evaluation methodology: `docs/EVALUATION_SUITE.md`

## Working Workflow for Every Task
1. **Plan first:** Inspect existing files and cross-check `docs/ARCHITECTURE.md` and `docs/IMPLEMENTATION_PLAN.md` before writing code.
2. **Small, verified increments:** Implement one vertical slice at a time (schema -> backend logic -> API endpoint -> UI -> test).
3. **Verify with real commands:** Run linters, typecheckers (`tsc --noEmit`, `ruff`, `mypy`), and unit/integration tests before marking any task complete. Never assume code compiles or passes without running it.
4. **Update progress:** Check off completed items in `docs/IMPLEMENTATION_PLAN.md` when verified.
