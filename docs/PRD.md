# Product Requirements Document (PRD)
## Project: ArchRadar — Living Architecture Mapper & PR Blast-Radius Radar

### 1. Problem Statement
Software documentation decays the week after it is written. Meanwhile, during Pull Request reviews, engineers frequently miss **non-obvious downstream side effects**—for example, changing a shared utility return type or middleware header that quietly breaks a webhook handler or billing worker three hops away.

Existing tools either:
- Generate static diagrams that immediately go stale, OR
- Dump raw diffs into an LLM without structural awareness of the codebase, causing vague or hallucinated code reviews.

### 2. Product Vision
**ArchRadar** combines **deterministic static code analysis (Tree-sitter)** with **grounded AI reasoning** to maintain a living, interactive architecture map of any GitHub repository and automatically score the **blast radius** of every Pull Request.

### 3. Target Users
1. **Tech Leads & Senior Engineers:** Need rapid visual insight into what a PR impacts before approving.
2. **New Engineers Onboarding:** Need an interactive, always-up-to-date map of how modules connect.
3. **Portfolio Reviewers / Hiring Managers (Crucial Meta-User):** Need a frictionless, zero-login **Interactive Live Demo** showing a pre-indexed real open-source repo + simulated PR blast-radius analysis in under 10 seconds.

### 4. MVP Scope (Version 1.0)
#### Must-Have Features (P0)
1. **Repository Ingestion & AST Indexing**
   - Paste a public GitHub repo URL (or pick from 2–3 pre-indexed demo repos).
   - Parse TypeScript/JavaScript and Python files using Tree-sitter.
   - Persist nodes (files, folders, exported symbols) and directed edges (imports/dependencies) in PostgreSQL.
2. **Interactive Living Architecture Canvas**
   - React Flow visualization with automatic hierarchical layout, folder grouping, zoom/minimap, and instant node search.
   - Click any file node to inspect: LOC, exported functions/classes, upstream dependencies ("imports"), downstream dependents ("imported by"), and centrality/risk score.
3. **PR Blast-Radius Radar (Deterministic + AI)**
   - Triggered automatically via **GitHub Webhook** (`pull_request` opened/synchronized) OR manually in the web UI by pasting a GitHub PR URL / diff.
   - **Deterministic step:** Highlight modified files, 1-hop dependents, and 2–3 hop transitive dependents directly on the graph.
   - **AI step:** Generate a structured **Blast-Radius Report** identifying silent breaking risks, impacted user/API flows, and a review checklist—with verified file citations.
4. **Living Docs Drift Detector**
   - Compare PR changes against the repo's `README.md` / `ARCHITECTURE.md` (if present) and propose a ready-to-copy Markdown diff patch whenever architecture docs become stale.
5. **Instant Portfolio Demo Mode**
   - Visitors land on a live interactive graph preloaded with sample PRs so they can click "Simulate PR #42" and watch the blast radius light up immediately without OAuth friction.

#### Nice-to-Have / V2 Features (P1 — Post-MVP)
- Automatic GitHub PR Comment Bot posting the blast-radius summary & mini-diagram back to GitHub.
- Historical Architecture Drift Timeline (slider comparing commit snapshots over time).
- Support for Go, Rust, and Java Tree-sitter grammars.
- Cost & latency telemetry dashboard per PR analysis.

### 5. Non-Functional Requirements
- **Indexing Speed:** Parse a 300-file repo in < 10 seconds.
- **Groundedness / Zero Phantom Files:** 100% of file paths cited in AI reports must be verified against the indexed AST graph.
- **Cost Efficiency:** Target < $0.01 per average PR analysis by sending only the diff + impacted subgraph rather than the full repository.
- **Security:** Read-only repository access; zero execution of untrusted repository code; strict webhook HMAC verification.

### 6. Portfolio Success Metrics (What Goes in Your README)
- Live deployed URL + 60-second demo GIF/video.
- Published Evaluation Report from `evals/` showing precision/recall on 30+ synthetic and real PRs.
- Architecture diagram + cost-per-1,000-PRs breakdown.
