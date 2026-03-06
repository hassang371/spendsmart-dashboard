# SCALE App — Architecture Overhaul Implementation Plan

**Goal:** Transform the tightly-coupled monorepo into a clean modular monolith (Approach A) with domain-separated FastAPI backend, pure React frontend, comprehensive security, monitoring, CI/CD, and full API design — all deployable for $0 initially.

**Architecture:** Modular monolith with domain modules (ingestion, categorization, forecasting, training, anomaly, accounts). Next.js becomes pure UI client. FastAPI handles all backend logic. Hybrid API protocol stack (REST + SSE + gRPC + Redis + Webhooks). Docker-first deployment targeting free tiers.

**Tech Stack:** Next.js 15 (frontend), FastAPI (backend), Supabase/Postgres (DB), Upstash Redis (cache/queue), Celery (worker), Docker, GitHub Actions (CI/CD), Sentry (monitoring).

---

## User Review Required

> [!IMPORTANT]
> This is a **massive undertaking**. The plan is structured into **5 milestones** that should be executed sequentially. Each milestone is independently deployable and valuable. I recommend we tackle **Milestone 1 first** (core backend restructure), get it working, then proceed to Milestone 2, and so on.

> [!WARNING]
> **Milestone 1 is the critical foundation.** It restructures the backend, eliminates all Next.js API routes, and fixes the 4 critical bugs from the audit. Everything else depends on this being solid. Estimated effort: 2-3 work sessions.

---

## Milestone Overview

| #      | Milestone                                   | What It Delivers                                                        | Dependencies |
| ------ | ------------------------------------------- | ----------------------------------------------------------------------- | ------------ |
| **M1** | Core Backend Restructure                    | Domain modules, all bugs fixed, Next.js API routes deleted              | None         |
| **M2** | API Design, OpenAPI & Database Optimization | Full OpenAPI spec, keyset pagination, index optimization, batch upserts | M1           |
| **M3** | Security Hardening                          | Redis rate limiting, CORS config, security headers, input validation    | M1           |
| **M4** | DevOps & CI/CD                              | Dockerfile (multi-target), docker-compose, GitHub Actions, staging/prod | M1           |
| **M5** | Monitoring & Observability                  | Structured logging, Sentry, health checks, request tracing, alerting    | M1, M4       |
| **M6** | SRE Foundation                              | SLOs, error budgets, runbooks, k6 load testing, chaos experiments       | M5           |

---

## Milestone 1: Core Backend Restructure

### System Design

```
┌──────────────────────────────────────────────────────────┐
│                     CLIENTS                               │
│   Next.js Web App (pure UI)  │  Mobile App (future)      │
│   (Vercel Edge)              │  (React Native)           │
└─────────┬────────────────────┴────────┬──────────────────┘
          │ REST (fetch)                │ REST
          ▼                             ▼
┌──────────────────────────────────────────────────────────┐
│                  FastAPI Gateway                          │
│  ┌─────────────────────────────────────────────────┐     │
│  │                   Core Layer                     │     │
│  │  Auth Middleware │ Error Handler │ Request ID    │     │
│  │  Structured Logger │ Rate Limiter │ CORS        │     │
│  └─────────────────────────────────────────────────┘     │
│                                                           │
│  ┌───────────┐ ┌──────────────┐ ┌─────────────────┐     │
│  │ Ingestion │ │Categorization│ │   Forecasting   │     │
│  │  Domain   │ │   Domain     │ │     Domain      │     │
│  │ • import  │ │ • classify   │ │  • forecast     │     │
│  │ • parse   │ │ • feedback   │ │  • predict      │     │
│  │ • dedup   │ │ • discover   │ │  • TFT train    │     │
│  └─────┬─────┘ └──────┬───────┘ └────────┬────────┘     │
│  ┌─────┴─────┐ ┌──────┴───────┐ ┌────────┴────────┐     │
│  │ Training  │ │   Anomaly    │ │    Accounts     │     │
│  │  Domain   │ │   Domain     │ │     Domain      │     │
│  │ • upload  │ │ • detect     │ │  • profile      │     │
│  │ • status  │ │ • alert      │ │  • settings     │     │
│  │ • jobs    │ │ • TDA        │ │  • transactions │     │
│  └───────────┘ └──────────────┘ └─────────────────┘     │
└────────────────────────┬─────────────────────────────────┘
                         │
           ┌─────────────┼──────────────┐
           ▼             ▼              ▼
      ┌─────────┐  ┌──────────┐  ┌──────────┐
      │Supabase │  │ Upstash  │  │  Celery  │
      │(Postgres)│  │ (Redis)  │  │  Worker  │
      └─────────┘  └──────────┘  └──────────┘
```

### Data Flow: Transaction Import (Current vs New)

**Current (broken):**

```
User → Next.js /api/import → Supabase directly (6-field fingerprint)
User → FastAPI /api/v1/training/upload → Supabase (3-field fingerprint)
Result: DUPLICATE DATA, INCONSISTENT FINGERPRINTS (BUG-02, ARCH-01)
```

**New (fixed):**

```
User → Next.js UI → fetch('FASTAPI_URL/api/v1/ingestion/import')
                     → FastAPI Ingestion Domain
                     → Unified fingerprint (SHA256, canonical fields)
                     → Supabase insert
Result: SINGLE SOURCE OF TRUTH
```

---

### Proposed Changes

#### Component 1: Domain Module Structure

##### [NEW] `apps/api/domains/__init__.py`

Empty init file for the domains package.

##### [NEW] `apps/api/domains/ingestion/router.py`

- Absorbs all logic from Next.js `POST /api/import` (219 lines)
- Absorbs `POST /api/decrypt-xlsx`, `POST /api/ingest`
- Consolidates fingerprinting into single `generate_fingerprint()` using canonical algorithm
- Pydantic schemas for all request/response bodies (fixes IMP-04)
- Endpoints: `POST /import`, `POST /parse`, `GET /uploaded-files`

##### [NEW] `apps/api/domains/ingestion/service.py`

- Business logic: file parsing, fingerprint generation, deduplication, batch insert
- Single `generate_fingerprint(date, amount, merchant, description, payment_method, reference)` function
- Used by both import and training paths (fixes BUG-02)

##### [NEW] `apps/api/domains/ingestion/schemas.py`

- `ImportTransactionRequest` — Pydantic model replacing raw `dict` bodies
- `ImportResponse` — standardized response with `inserted`, `skipped_duplicates`, `skipped_zero_amount`

##### [MODIFY] `apps/api/domains/categorization/router.py`

- Moves logic from `classify.py` and the classify part of `ingestion.py`
- **Fixes BUG-03**: Single `/classify` endpoint (no more conflict)
- **Fixes BUG-04**: Batch classify runs in-process (no N+1 Celery)
- **Fixes ARCH-04**: HypCD classifier as singleton via FastAPI lifespan
- Endpoints: `POST /classify`, `POST /classify/batch`, `POST /feedback`

##### [NEW] `apps/api/domains/forecasting/router.py`

- Moves logic from `forecast.py`
- Fixes BUG-07: Uses correct parser, preserves metadata columns
- Endpoints: `POST /forecast/upload`, `GET /forecast/{user_id}`

##### [MODIFY] `apps/api/domains/training/router.py`

- Moves logic from `training.py`
- **Fixes BUG-01**: Celery task updates `training_jobs` table with status/metrics via service-role client
- Endpoints: `POST /training/upload`, `GET /training/status/{job_id}`, `GET /training/checkpoints`

##### [NEW] `apps/api/domains/anomaly/router.py`

- Placeholder for future TDA anomaly detection
- Endpoints: `GET /anomaly/alerts/{user_id}` (stub)

##### [NEW] `apps/api/domains/accounts/router.py`

- Absorbs Next.js `GET /api/transactions`
- Endpoints: `GET /transactions`, `GET /profile`, `PUT /settings`

---

#### Component 2: Core Infrastructure

##### [MODIFY] `apps/api/core/auth.py`

- Centralized auth middleware: validates Supabase JWT, extracts `user_id`
- Replaces per-router auth logic in current `supabase_client.py`
- **Fixes BUG-06**: Validates token expiry upfront, returns clear 401 with reason

##### [NEW] `apps/api/core/errors.py`

- Centralized exception handler middleware
- **Fixes ARCH-02**: All errors go through one handler
- RFC 7807 Problem Details format for all error responses
- Request ID in every response for traceability

##### [NEW] `apps/api/core/logging.py`

- Structured JSON logging with `structlog`
- Every log entry: timestamp, level, service, request_id, user_id
- **Replaces all `print()` statements** in forecast.py and elsewhere

##### [MODIFY] `apps/api/main.py`

- Registers all domain routers under `/api/v1`
- Adds error handler middleware, request ID middleware
- **Fixes ARCH-03**: CORS origins from environment variable
- FastAPI lifespan for singleton initialization (HypCD classifier)

##### [MODIFY] `apps/api/requirements.txt`

- **Fixes ARCH-05**: Removes `google-generativeai`
- Adds: `structlog`, `python-json-logger`

---

#### Component 3: Frontend Cleanup

##### [DELETE] `apps/web/app/api/import/route.ts`

All logic moves to `ingestion/router.py`.

##### [DELETE] `apps/web/app/api/decrypt-xlsx/` (directory)

Logic moves to `ingestion/router.py`.

##### [DELETE] `apps/web/app/api/ingest/` (directory)

Logic moves to `ingestion/router.py`.

##### [DELETE] `apps/web/app/api/transactions/` (directory)

Logic moves to `accounts/router.py`.

##### [MODIFY] `apps/web/lib/api/client.ts`

New centralized API client that calls FastAPI backend. Single `NEXT_PUBLIC_API_URL` env var. All components use this instead of calling Supabase directly for backend operations.

---

#### Component 4: Worker Fix

##### [MODIFY] `apps/api/tasks/training_tasks.py`

- **Fixes BUG-01**: Creates a service-role Supabase client inside the Celery task
- Updates `training_jobs` table with `status: "completed"` or `status: "failed"`, plus `metrics` and `checkpoint_path`

---

## Milestone 2: API Design & OpenAPI

### Proposed Changes

##### [NEW] `apps/api/core/pagination.py`

- Cursor-based pagination for collection endpoints (transactions, training jobs)
- Standard `PaginatedResponse[T]` generic model

##### [NEW] `apps/api/core/filtering.py`

- Query parameter filtering: date range, amount range, category, merchant
- Reusable `TransactionFilter` dependency

##### [MODIFY] All domain `schemas.py` files

- Comprehensive Pydantic models with examples, descriptions
- OpenAPI documentation auto-generated from schemas
- Consistent `snake_case` naming
- Error response catalog with all possible error codes

##### [NEW] `apps/api/core/versioning.py`

- API version prefix management
- Deprecation header support for future `/api/v2`

---

## Milestone 3: Security Hardening

### Proposed Changes

##### [MODIFY] `apps/api/core/rate_limiter.py`

- **Fixes BUG-05**: Redis-backed rate limiting via Upstash
- Per-user rate limits: 100 req/min general, 10 req/min auth endpoints
- Sliding window algorithm

##### [MODIFY] `apps/api/core/auth.py`

- JWT validation with expiry check
- Role-based access control (RBAC) preparation
- Security headers middleware (X-Content-Type-Options, X-Frame-Options, etc.)

##### [MODIFY] `apps/api/main.py`

- CORS: configurable via `ALLOWED_ORIGINS` env var (comma-separated)
- HTTPS enforcement in production
- Request size limits

##### [NEW] `apps/api/core/security_headers.py`

- Helmet-equivalent middleware for FastAPI
- CSP, HSTS, X-Frame-Options, X-Content-Type-Options

---

## Milestone 4: DevOps & CI/CD

### Proposed Changes

##### [MODIFY] `Dockerfile`

- Multi-stage build: builder (install deps) → runtime (slim image)
- Non-root user, health check, proper signal handling
- Separate targets for API and worker

##### [MODIFY] `docker-compose.yml`

- Services: `api`, `worker`, `redis`, `postgres` (for local dev)
- Health checks for all services
- Volume mounts for development hot-reload

##### [NEW] `.github/workflows/ci.yml`

- Trigger: push to `main`, PRs
- Steps: lint (ruff + eslint), type check (mypy + tsc), test (pytest + vitest), build Docker image
- Security: container scanning with Trivy

##### [NEW] `.github/workflows/deploy.yml`

- Deploy to Railway/Render on merge to `main`
- Environment-specific configs (staging vs production)

##### [NEW] `.env.example` (updated)

- All required env vars documented with descriptions
- `FASTAPI_URL`, `ALLOWED_ORIGINS`, `REDIS_URL`, `SUPABASE_SERVICE_ROLE_KEY`

---

## Milestone 5: Monitoring & Observability

### Proposed Changes

##### [NEW] `apps/api/core/middleware/request_id.py`

- Generates UUID for every request
- Attaches to all logs and response headers (`X-Request-ID`)

##### [MODIFY] `apps/api/core/logging.py`

- Structured JSON logs with: timestamp, level, service, request_id, user_id, duration_ms, status_code
- Log level from env var (`LOG_LEVEL=info`)

##### [MODIFY] `apps/api/domains/health/router.py` (renamed from `routers/health.py`)

- **Fixes IMP-05**: Non-blocking health check (Redis ping, not Celery inspect)
- Separate `/health` (liveness) and `/ready` (readiness) endpoints
- Version info in health response

##### [NEW] Sentry integration in `apps/api/main.py`

- Error tracking with Sentry DSN from env var
- Performance monitoring (transaction tracing)
- User context attachment

---

## Verification Plan

### Automated Tests

All existing tests should continue to pass after restructuring. The domain modules will need new test files:

**Existing tests to migrate** (currently in `apps/api/tests/`):

- `test_health.py` → verify health endpoint still works
- `test_classify.py`, `test_classify_endpoint.py` → move to `domains/categorization/tests/`
- `test_ingestion.py` → move to `domains/ingestion/tests/`
- `test_forecast.py` → move to `domains/forecasting/tests/`
- `test_hypcd_integration.py` → move to `domains/categorization/tests/`
- `test_api_payload_construction.py` → move to relevant domain

**New tests to write** (per domain):

- `test_fingerprint_consistency.py` — verify Python fingerprint matches the canonical algorithm (fixes BUG-02)
- `test_training_status_update.py` — verify Celery task writes status to DB (fixes BUG-01)
- `test_singleton_classifier.py` — verify HypCD is initialized once (fixes ARCH-04)
- `test_error_handler.py` — verify RFC 7807 error format (fixes ARCH-02)
- `test_rate_limiter.py` — verify Redis-backed rate limits (fixes BUG-05)

**Commands to run tests:**

```bash
# Backend tests (from project root)
cd /Users/hassangameryt/Documents/Antigravity/SCALE\ APP
python -m pytest apps/api/tests/ -v

# Frontend tests
cd apps/web
npx vitest run

# Specific domain tests
python -m pytest apps/api/domains/ingestion/tests/ -v
python -m pytest apps/api/domains/categorization/tests/ -v
```

### Manual Verification

1. **Import Flow**: Upload a CSV via the Next.js UI → confirm it hits FastAPI (not the old Next.js API route) → verify data appears in Supabase with correct fingerprint
2. **Classification**: Send a POST to `/api/v1/categorization/classify` → verify HypCD response
3. **Health Check**: `curl http://localhost:8000/api/v1/health` → verify JSON response with status, version, DB connectivity
4. **CORS**: Load the Next.js frontend → verify no CORS errors in browser console when calling FastAPI
5. **Error Format**: Send a malformed request → verify RFC 7807 error response with request_id

### Docker Verification

```bash
# Build and run
docker compose up --build

# Verify API is running
curl http://localhost:8000/api/v1/health

# Verify worker is running
docker compose logs worker | grep "ready"
```
