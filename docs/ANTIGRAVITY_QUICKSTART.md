# Google Antigravity Quickstart Guide — ArchRadar

Follow these steps to initialize **ArchRadar** in Google Antigravity and let the agent work cleanly from your specification documents.

## Step 1: Unzip & Initialize Git
```bash
cd archradar
git init
git add .
git commit -m "chore: add Antigravity rules and ArchRadar project specs"
```

## Step 2: Create a Project in Google Antigravity
1. Open **Google Antigravity** (App, IDE, or CLI).
2. Click **Projects -> New Project** and select your `archradar` folder.
3. Verify rules loaded properly:
   - Open **Customizations -> Rules** (or Project Settings -> Customizations).
   - Confirm Antigravity detected `GEMINI.md` and the three files under `.agents/rules/`.
4. Set your preferred **Permission Preset** (recommended: **Default** or **Request Review** while scaffolding so you can review shell commands and file changes).

## Step 3: Your First 3 Kickoff Prompts (Copy & Paste)

### Prompt 1 — Phase 0 Bootstrap (Start Here)
> Read `GEMINI.md`, `docs/ARCHITECTURE.md`, and `docs/IMPLEMENTATION_PLAN.md`. Let's start **Phase 0: Workspace & Infrastructure Bootstrap**. First present a short implementation plan, then scaffold `docker-compose.yml`, `.env.example`, `.gitignore`, the FastAPI backend (`apps/api`), and the Next.js 15 TypeScript frontend (`apps/web`). Verify both apps build/typecheck cleanly and update Phase 0 checkboxes in `docs/IMPLEMENTATION_PLAN.md`.

### Prompt 2 — Phase 1 Tree-sitter AST Engine (Start in a New Conversation or Worktree)
> Read `docs/ARCHITECTURE.md` and `.agents/rules/backend-parser-ai.md`. Implement **Phase 1: Deterministic AST Engine** in `apps/api`. Build the `LanguageAdapter` base class, `TypeScriptAdapter`, `PythonAdapter`, and `RepoIndexer`, plus comprehensive unit tests in `apps/api/tests/test_parser.py` covering relative imports, `@/` aliases, barrel files, and circular imports. Run `pytest` and `ruff check .` to verify everything passes.

### Prompt 3 — Phase 2 Blast-Radius & Grounded AI Pipeline
> Read `docs/ARCHITECTURE.md`, `docs/EVALUATION_SUITE.md`, and `.agents/rules/backend-parser-ai.md`. Implement **Phase 2: Blast-Radius Engine & Grounded AI Pipeline**. Build reverse-BFS blast-radius calculation, Pydantic structured schemas, the Gemini-backed AI analyzer with post-LLM file citation verification, and the HMAC-verified GitHub webhook endpoint. Verify all tests pass before checking off Phase 2.

## Pro Tips for Working in Antigravity
- **Use New Worktree Mode** when tackling big features (like the React Flow canvas or AST parser) so the agent works in an isolated Git worktree without polluting your main branch.
- **One Phase per Conversation:** Start a fresh conversation for each phase so the agent's context stays crisp and focused—your `GEMINI.md`, `.agents/rules/*.md`, and `docs/IMPLEMENTATION_PLAN.md` automatically carry all persistent context forward!
- **Reference docs explicitly with `@`:** You can type `@docs/ARCHITECTURE.md` or `@docs/PRD.md` in any prompt to focus the agent on a specific spec.
