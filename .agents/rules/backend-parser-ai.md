---
trigger: glob
globs: "apps/api/**/*.py"
description: Coding standards for FastAPI, Tree-sitter AST parsing, graph traversal, and structured AI pipelines.
---

# Backend, AST Parser & AI Pipeline Rules (Python + FastAPI)

## Stack & Conventions
- Target **Python 3.12+** with full type hints on every function signature.
- Use **FastAPI** with async endpoints, **SQLAlchemy 2.0 (async)**, **PostgreSQL**, and **Pydantic v2** models.
- Format and lint with `ruff`; type-check with `mypy` or `pyright`.

## Tree-sitter Static Analysis Rules
- Support **TypeScript / JavaScript** and **Python** in MVP (extensible via a clean `LanguageAdapter` base class).
- Extract:
  1. File nodes (path, language, LOC, module group/folder)
  2. Exported symbols (functions, classes, interfaces, routes/webhooks)
  3. Directed dependency edges (`imports`, `calls` where resolvable, `re-exports`)
- Handle relative paths, path aliases (`tsconfig.json` `@/` paths), and index barrel files (`index.ts` / `__init__.py`) gracefully without crashing on unresolved third-party packages.

## Blast-Radius & AI Reasoning Rules
- **Deterministic Graph Traversal:** Compute upstream and downstream impacted files (BFS up to configurable depth, default `max_depth=3`) purely in Python/SQL before calling any LLM.
- **Token Budget Control:** Never feed an entire repo into the LLM prompt. Pass ONLY:
  1. The unified PR diff (truncated cleanly if huge)
  2. The impacted subgraph JSON (modified nodes + downstream dependents + exported symbol signatures)
  3. Any relevant existing architecture doc snippet
- **Structured AI Output:** Enforce a strict Pydantic response model containing:
  - `overall_risk` (`low | medium | high | critical`)
  - `summary` (concise plain-English overview)
  - `impacted_flows` (list of broken/at-risk downstream features with **exact cited file paths** that must exist in the deterministic graph)
  - `doc_drift_alerts` (specific outdated sections + suggested Markdown patch)
  - `review_checklist` (actionable verification items for the PR author)
- **Citation Verification:** Post-validate that every file path cited by the LLM actually exists in the repository graph; flag or strip hallucinated paths automatically.

## Quality Checks
- Run `pytest` and `ruff check .` inside `apps/api` before finishing backend changes.
