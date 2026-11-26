---
trigger: always_on
description: Core security boundaries, secret handling, and mandatory verification standards across the entire repository.
---

# Security & Verification Invariants

## Security Rules
- **Never commit secrets:** API keys (`GEMINI_API_KEY`, `GITHUB_WEBHOOK_SECRET`, `GITHUB_APP_PRIVATE_KEY`, `DATABASE_URL`) must ONLY live in `.env` (gitignored) and be documented as empty placeholders in `.env.example`.
- **Verify GitHub Webhooks:** Every incoming GitHub webhook MUST validate the `X-Hub-Signature-256` HMAC signature using constant-time comparison (`hmac.compare_digest`) before parsing or queuing payloads.
- **Safe repository cloning/parsing:** Never execute code from an analyzed repository. Tree-sitter parses raw source text only; never run `npm install`, `python`, or shell scripts from target repos.
- **Prevent path traversal:** Normalize and validate all file paths extracted from git diffs or AST imports against the repository root.

## Engineering & Verification Rules
- **Evidence before completion:** After modifying code, run the relevant test suite and typechecker and confirm zero errors.
- **No silent fallbacks:** Do not swallow exceptions with empty `except:` or `catch {}` blocks. Log structured errors with correlation IDs.
- **Schema-first contracts:** If an API response shape changes in `apps/api`, update the corresponding TypeScript types / Zod schemas in `apps/web` in the same task.
