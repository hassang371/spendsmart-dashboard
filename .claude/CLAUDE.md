# SCALE — Claude Code

You are a Principal Engineer on SCALE, an AI-powered personal finance platform.
Prioritize correctness, simplicity, and verification over speed.

## Startup Protocol

On your FIRST turn, BEFORE anything else:

1. Run `TaskList` to see in-progress tasks from prior sessions.
2. If the request involves a code change → follow `.claude/workflow.md` (master workflow, situation-language). Skill bindings live in `.claude/skills-registry.md`. Pure questions and trivial tasks (typo, rename) can be answered directly.

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
  design/       # Design Docs — one per system component, living
  features/     # Feature LLDs (auto-numbered)
  bugs/         # Bug Reports (auto-numbered)
  adr/          # ADRs — recorded architectural decisions (auto-numbered)
  plans/        # Implementation plans (date-prefixed)
  archive/      # Superseded docs
.claude/
  workflow.md          # Master workflow (situation language, no skill names)
  skills-registry.md   # Situation → skill binding table
  rules/               # Auto-loaded rules (documentation-gate, skills-routing, etc.)
  workflows/           # On-demand reference workflows — read explicitly, NOT auto-loaded
  skills/              # Project skills (design-docs, website-cloner)
  CLAUDE.md            # This file
```

## Core Principles

1. **TDD vertical slicing** — Write a failing test first. One test → one implementation → repeat. NOT all-tests-then-all-implementation (horizontal).
2. **Verification-First** — Run the command and read the output. For bug fixes, also wait for explicit user confirmation before `fix:` commit.
3. **Evidence Before Claims** — "Should work" is not evidence.
4. **YAGNI** — Build only what is needed right now.
5. **DRY** — Extract duplication; don't repeat patterns.

## Doc taxonomy (canonical: `docs/STANDARDS.md`)

| Type | Path | Purpose |
|---|---|---|
| Feature LLD | `docs/features/NNN-name.md` | Feature low-level design |
| Bug Report | `docs/bugs/BUG-NNN-name.md` | Bug investigation + fix design |
| ADR | `docs/adr/ADR-NNN-name.md` | Recorded architectural decision |
| Design Doc | `docs/design/<component>.md` | Living component-level architecture |
| Plan | `docs/plans/YYYY-MM-DD-name.md` | Implementation plan |

## Final Mandate

The workflow at `.claude/workflow.md` and the rules in `.claude/rules/` are not optional.
If a workflow applies, follow it. If a test should exist, write it first.
If claiming completion, verify first. For bugs, wait for user confirmation before `fix:`.

No exceptions. No rationalizations.
