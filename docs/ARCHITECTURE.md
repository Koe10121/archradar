# System Architecture Specification — ArchRadar

## 1. High-Level System Flow

```text
[GitHub Repo / PR Webhook]
          │
          ▼
┌─────────────────────────────┐      ┌──────────────────────────────────┐
│  FastAPI Ingestion Service  │─────▶│  Redis / Background Worker       │
│  - HMAC Signature Check     │      │  1. Fetch git tree / PR diff     │
│  - REST API for Frontend    │      │  2. Tree-sitter AST Parser       │
└─────────────────────────────┘      │  3. Resolve Imports & Symbols    │
          │                          │  4. Compute Blast Radius (BFS)   │
          │                          │  5. Grounded LLM Risk Analysis   │
          ▼                          │  6. Citation & Schema Validator  │
┌─────────────────────────────┐      └────────────────┬─────────────────┘
│  PostgreSQL Database        │◀──────────────────────┘
│  - repositories             │
│  - graph_snapshots          │
│  - file_nodes & edges       │
│  - pr_analyses              │
└─────────────────────────────┘
          │
          ▼
┌─────────────────────────────┐
│  Next.js 15 Frontend        │
│  - React Flow Graph Canvas  │
│  - Blast-Radius Heatmap     │
│  - AI Risk & Drift Drawer   │
│  - Zero-Auth Demo Mode      │
└─────────────────────────────┘
```

## 2. Tech Stack Choices & Rationale

| Layer | Technology | Why |
| :--- | :--- | :--- |
| **Frontend** | Next.js 15 (App Router), TypeScript, Tailwind CSS, shadcn/ui | Fast SSR, clean component ergonomics, industry standard. |
| **Graph Canvas** | `@xyflow/react` (React Flow) + Dagre/ELKjs | Best-in-class interactive node graph for developer tools. |
| **Backend API** | FastAPI (Python 3.12), Pydantic v2 | Strong typing, async I/O, first-class Tree-sitter & AI SDK support. |
| **Static Analysis** | `tree-sitter`, `tree-sitter-typescript`, `tree-sitter-python` | Fast, fault-tolerant, deterministic AST parsing across languages. |
| **Database** | PostgreSQL 16 + SQLAlchemy 2.0 (async) + Alembic | Relational graph storage with JSONB for structured AI reports & symbols. |
| **Task Queue** | Redis + ARQ (or Celery / FastAPI BackgroundTasks for local MVP) | Non-blocking repo indexing and webhook processing. |
| **AI Model Layer** | Pluggable LLM provider (Gemini API default via `google-genai` SDK) | Native structured JSON output, fast latency, low cost per PR. |

## 3. Core Database Schema

### `repositories`
- `id` (UUID, PK)
- `owner` (text), `name` (text), `url` (text, unique)
- `default_branch` (text)
- `is_demo` (boolean, default false)
- `last_indexed_sha` (text)
- `created_at`, `updated_at` (timestamptz)

### `graph_snapshots`
- `id` (UUID, PK)
- `repository_id` (UUID, FK -> `repositories.id`)
- `commit_sha` (text)
- `file_count` (int), `edge_count` (int)
- `status` (`pending | indexing | ready | failed`)
- `created_at` (timestamptz)

### `file_nodes`
- `id` (UUID, PK)
- `snapshot_id` (UUID, FK -> `graph_snapshots.id`)
- `path` (text — repo-relative normalized path, e.g. `src/services/auth.ts`)
- `language` (text — `typescript | javascript | python | other`)
- `module_group` (text — top-level folder or package name)
- `loc` (int)
- `exports_json` (JSONB — list of `{name, kind, signature}`)
- `in_degree` (int — count of files importing this file; key centrality metric)
- `out_degree` (int — count of files this file imports)

### `dependency_edges`
- `id` (UUID, PK)
- `snapshot_id` (UUID, FK -> `graph_snapshots.id`)
- `source_node_id` (UUID, FK -> `file_nodes.id`) — the importing file
- `target_node_id` (UUID, FK -> `file_nodes.id`) — the imported file
- `edge_type` (text — `import | re_export | dynamic_import`)
- `imported_symbols` (JSONB — e.g. `["verifyToken", "UserSession"]`)

### `pr_analyses`
- `id` (UUID, PK)
- `repository_id` (UUID, FK -> `repositories.id`)
- `snapshot_id` (UUID, FK -> `graph_snapshots.id`)
- `pr_number` (int, nullable for ad-hoc diff simulations)
- `pr_title` (text)
- `changed_files` (JSONB — list of file paths modified in diff)
- `blast_radius_json` (JSONB — `{direct: [...], hop_1: [...], hop_2: [...], hop_3: [...]}`)
- `ai_report_json` (JSONB — validated `BlastRadiusReport` Pydantic schema)
- `model_used` (text), `prompt_tokens` (int), `completion_tokens` (int), `estimated_cost_usd` (numeric)
- `latency_ms` (int)
- `created_at` (timestamptz)

## 4. Deterministic Blast-Radius Algorithm

Given a set of modified file paths `M` from a PR diff:
1. Map each path in `M` to its `file_node` in the latest `graph_snapshot`.
2. Build the **reverse adjacency list** (`target_node_id -> [source_node_ids]`), because if file `A` changes, every file `B` that imports `A` is downstream impacted.
3. Run **Breadth-First Search (BFS)** starting from `M` up to `max_depth = 3`:
   - Depth 0: Directly modified files (`changed_files`)
   - Depth 1: Direct dependents (files importing a changed file)
   - Depth 2–3: Transitive dependents (files importing a depth 1–2 file)
4. Compute a deterministic **Blast-Radius Score (0–100)** based on:
   - Number of impacted files as a % of repo size
   - Maximum `in_degree` (hub/core utility penalty)
   - Whether changed symbols (`exports_json`) match `imported_symbols` on outgoing reverse edges (high-signal precision filter!)
   - Whether sensitive boundaries are touched (e.g., `auth`, `webhook`, `db`, `schema`, `middleware`).

## 5. Grounded AI Analysis Pipeline

### Input Context (Strict Token Budget)
1. PR title, description, and unified git diff (capped at ~12k chars, prioritizing changed function signatures).
2. Deterministic blast-radius subgraph JSON (only Depth 0, 1, and high-centrality Depth 2 nodes + exact imported symbols).
3. Relevant excerpts from `README.md` / `docs/ARCHITECTURE.md` (if present).

### Output Contract (`BlastRadiusReport` Pydantic Model)
```python
class ImpactedFlow(BaseModel):
    title: str
    severity: Literal["low", "medium", "high", "critical"]
    entry_file: str          # Must exist in snapshot graph
    affected_files: list[str] # Every path verified against snapshot graph
    explanation: str
    suggested_test: str

class DocDriftAlert(BaseModel):
    doc_file: str
    section: str
    reason: str
    suggested_markdown_patch: str

class BlastRadiusReport(BaseModel):
    overall_risk: Literal["low", "medium", "high", "critical"]
    confidence: float  # 0.0 to 1.0
    executive_summary: str
    breaking_change_detected: bool
    impacted_flows: list[ImpactedFlow]
    doc_drift_alerts: list[DocDriftAlert]
    reviewer_checklist: list[str]
```

### Post-LLM Verification Gate
Before persisting `ai_report_json`:
- Verify every path in `entry_file` and `affected_files` exists in `file_nodes` for that snapshot.
- Strip or mark any unverified path and log a `hallucination_caught` telemetry metric.

## 6. REST API Endpoints (MVP)
- `POST /api/repos/index` — Submit a GitHub repo URL to clone/fetch & index.
- `GET /api/repos` — List indexed repositories (including preloaded demo repos).
- `GET /api/repos/{repo_id}/graph` — Fetch nodes, edges, and metrics for React Flow.
- `POST /api/repos/{repo_id}/analyze-pr` — Analyze a GitHub PR URL or raw unified diff.
- `GET /api/analyses/{analysis_id}` — Retrieve full blast-radius + AI report.
- `POST /api/webhooks/github` — Receive real GitHub `pull_request` webhooks (HMAC-verified).
- `GET /api/health` — Service + DB health check.

## 7. Estimated Unit Economics (For Portfolio README)
- Average PR prompt: ~4,000 input tokens + ~900 output tokens.
- At Gemini Flash-class pricing, 1,000 PR analyses cost roughly **$0.40 – $1.50 total**, making the system genuinely viable for real teams.
