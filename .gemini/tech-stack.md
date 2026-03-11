# SCALE — Tech Stack Reference

Loaded by `brainstorm.md` at the start of every brainstorm session. Provides the canonical stack so Gemini doesn't rediscover it from source files each time.

---

## Frontend (`apps/web/`)

| Layer | Technology |
|---|---|
| Framework | Next.js 16 (App Router — no `pages/`) |
| Language | TypeScript 5 (strict mode, no `any`) |
| Runtime | React 19 |
| Styling | Tailwind CSS only — no inline styles, no CSS modules |
| Auth / DB | Supabase SSR (`@supabase/ssr`) |
| HTTP client | `apps/web/lib/api/client.ts` — never call `fetch` directly |
| Testing | Vitest + Playwright |
| Monitoring | Sentry (browser), Vercel Speed Insights |

### Key Conventions
- Server Components by default — `"use client"` only when browser APIs or hooks are required
- Supabase server client: `import { createClient } from "@/lib/supabase/server"` (never in client components)
- Supabase client component: `import { createClient } from "@/lib/supabase/client"`
- Run `npx tsc --noEmit` before claiming done
- Landing page (`/`) uses Webflow HTML injection — handle with care

---

## Backend (`apps/api/`)

| Layer | Technology |
|---|---|
| Framework | FastAPI 0.115 |
| Language | Python 3.14 |
| Server | Uvicorn |
| Auth | JWT + Supabase |
| Rate limiting | Redis-backed sliding window |
| Logging | structlog + Sentry |
| Error format | RFC 9457 Problem Detail |

### Domain Structure
```
apps/api/domains/<domain>/
  router.py     ← thin, delegates to service
  service.py    ← business logic
  schemas.py    ← Pydantic models
  tests/
```

Active domains: `ingestion`, `categorization`, `forecasting`, `training`, `anomaly`, `accounts`

### Key Conventions
- Supabase client via dependency injection — never instantiate directly in handlers
- Max upload: 500 MB (large bank statement files)
- Security headers middleware active (X-Frame-Options, CSP, HSTS)

---

## Worker (`apps/worker/`)

| Layer | Technology |
|---|---|
| Queue | Celery 5 + Redis |
| Language | Python 3.14 |
| ML training | PyTorch Lightning + PyTorch Forecasting (TFT) |
| State machine | `job_states.py` (PENDING → PROCESSING → COMPLETED/FAILED) |

### Key Conventions
- Tasks dispatch via `.delay()` or `.apply_async()` — never call task functions directly
- Worker polls `training_jobs` table in Supabase for PENDING jobs
- Env loaded from root `.env` only (`SUPABASE_URL` or `NEXT_PUBLIC_SUPABASE_URL` fallback)

---

## Shared Packages (`packages/`)

| Package | Purpose | Model |
|---|---|---|
| `categorization/` | Transaction classifier | MiniLM v2 (cosine similarity, threshold 0.65) |
| `forecasting/` | Financial predictions | Temporal Fusion Transformer (TFT) |
| `ingestion_engine/` | CSV/Excel parsing | Pandas + openpyxl/xlrd |

---

## Infrastructure

| Component | Technology |
|---|---|
| Database | Supabase (Postgres + Auth + Storage + Realtime) |
| Cache / Queue | Redis |
| Containers | Docker Compose (api, worker, flower, redis) |
| Frontend host | Vercel |
| Monitoring | Sentry (server + browser) |

---

## Dev Commands

```bash
make dev        # Start frontend :3000 + backend :8000
make worker     # Start Celery worker
make stop       # Kill servers (logs preserved)
make logs       # Stream all logs
make test       # pytest apps/ packages/ (backend + worker)
make test-fe    # Vitest (frontend)
make check      # lint + tsc + pytest (full DoD — run before claiming done)
make install    # pip install + npm install
```

---

## Testing

| Layer | Tool | Command |
|---|---|---|
| Backend + worker | pytest | `.venv/bin/python -m pytest apps/ packages/ -v` |
| Frontend | Vitest | `cd apps/web && npm test` |
| Type check | tsc | `cd apps/web && npx tsc --noEmit` |
| Lint | ESLint + Ruff | `cd apps/web && npm run lint` |

---

## Key File Paths

| What | Where |
|---|---|
| API entry point | `apps/api/main.py` |
| Config / env vars | `apps/api/core/config.py` |
| Worker entry | `apps/worker/main.py` |
| Next.js root layout | `apps/web/app/layout.tsx` |
| API HTTP client | `apps/web/lib/api/client.ts` |
| Supabase helpers | `apps/web/lib/supabase/client.ts`, `server.ts` |
| HLD docs | `docs/design/` |
| Feature LLDs | `docs/features/NNN-name.md` |
| Bug reports | `docs/bugs/BUG-NNN-name.md` |
| RFCs | `docs/rfcs/RFC-NNN-name.md` |
