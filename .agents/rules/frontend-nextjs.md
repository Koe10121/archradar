---
trigger: glob
globs: "apps/web/**/*.{ts,tsx,css}"
description: Coding conventions, UI/UX standards, and React Flow performance rules for the Next.js frontend.
---

# Frontend Engineering Rules (Next.js + React Flow)

## Stack & Conventions
- Use **Next.js App Router** with **TypeScript (strict mode)** and **Tailwind CSS**.
- Validate all external API responses at the boundary with **Zod**.
- Keep React Server Components for initial page data fetching and isolate interactive graph/canvas logic inside explicit `"use client"` components.

## React Flow & Graph Visualization Rules
- **Performance:** Memoize custom node and edge components with `React.memo`, and define `nodeTypes` and `edgeTypes` outside component render functions to prevent unnecessary re-renders.
- **Layout:** Run Dagre or ELK layout calculations deterministically (ideally cached or offloaded) so node positions remain stable across filter toggles.
- **Blast-Radius Visual Hierarchy:**
  - Directly modified files: high-contrast accent ring (`#F59E0B` amber).
  - 1-hop downstream dependents: warning tint (`#EF4444` red).
  - 2+ hop transitive dependents: softer highlight (`#FCA5A5`).
  - Unaffected nodes: dimmed opacity (`0.25`) when PR Blast-Radius mode is active.
- **UX Polish:** Support node search, click-to-inspect side drawer (showing symbol exports, incoming/outgoing edges, and AI risk notes), and a one-click "Demo Repo" mode so portfolio visitors do not need to log into GitHub to explore the app.

## Quality Checks
- Run `npm run lint` and `npx tsc --noEmit` inside `apps/web` before finishing frontend changes.
