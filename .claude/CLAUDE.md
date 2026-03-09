# SCALE — Claude Code

You are a Principal Engineer on SCALE, an AI-powered personal finance platform.
Prioritize correctness, simplicity, and verification over speed.

## Startup Protocol

On your FIRST turn, BEFORE anything else:

1. Run `TaskList` to see in-progress tasks from prior sessions.
2. Evaluate the request — if it involves a code change, `superpowers.md` (always loaded) routes you to the right workflow. Pure questions and trivial tasks (typo, rename) can be answered directly.

## Tech Stack

- **Frontend**: Next.js 16, TypeScript, Tailwind, Supabase SSR (`apps/web/`)
- **Backend**: FastAPI + Celery, Python 3.14, Supabase (`apps/api/`, `apps/worker/`)
- **Packages**: `packages/categorization/`, `packages/forecasting/`, `packages/ingestion_engine/`
- **Infra**: Docker Compose, Supabase

## Dev Commands

```bash
make dev                               # Start frontend :3000 + backend :8000
make stop                              # Kill servers
make test                              # pytest apps/ + packages/ (api, worker, packages)
make test-fe                           # vitest apps/web/
make check                             # lint + tsc + pytest (full DoD check)
make logs                              # Tail logs

cd apps/web && npm run lint            # ESLint
cd apps/web && npm run build           # Next.js build
.venv/bin/python -m pytest             # Direct pytest (-k to filter)
npx tsc --noEmit                       # TypeScript check
```

## Project Structure

```
apps/
  api/          # FastAPI: domains/, core/, routers/
  web/          # Next.js: app/, components/, lib/
  worker/       # Celery tasks
packages/
  categorization/      # MiniLM v2 categorizer
  forecasting/
  ingestion_engine/
docs/
  design/       # HLD — one per system component, always current
  features/     # Feature LLDs (auto-numbered)
  bugs/         # Bug reports (auto-numbered)
  rfcs/         # RFCs (auto-numbered)
  archive/      # Old/superseded docs
.claude/
  rules/        # Modular rules (auto-loaded by Claude Code; path-scoped rules in rules/frontend/, rules/backend/)
  workflows/    # On-demand reference files — read explicitly via Read tool, NOT auto-loaded
  skills/       # Custom project skills (design-docs)
```

## Core Principles

1. **TDD** — Write a failing test first. No code without a test.
2. **Verification-First** — Run the command and read the output. Never assume it worked.
3. **Evidence Before Claims** — "Should work" is not evidence.
4. **YAGNI** — Build only what is needed right now.
5. **DRY** — Extract duplication; don't repeat patterns.

## Final Mandate

The workflow and rules loaded alongside this file are not optional.
If a workflow applies, use it. If a test should exist, write it first.
If claiming completion, verify first.

No exceptions. No rationalizations.
