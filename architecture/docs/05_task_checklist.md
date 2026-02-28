# SCALE App Architecture Overhaul — Tasks

## Milestone 1: Core Backend Restructure

### 1.1 Domain Module Scaffold

- [ ] Create `apps/api/domains/` package with `__init__.py`
- [ ] Create domain subpackages: `ingestion/`, `categorization/`, `forecasting/`, `training/`, `anomaly/`, `accounts/`
- [ ] Each domain gets: `router.py`, `service.py`, `schemas.py`, `tests/__init__.py`

### 1.2 Core Infrastructure

- [ ] Create `apps/api/core/` package
- [ ] Create `core/auth.py` — centralized JWT validation middleware
- [ ] Create `core/errors.py` — RFC 7807 error handler + exception classes
- [ ] Create `core/logging.py` — structured JSON logging with structlog
- [ ] Create `core/config.py` — Pydantic settings for env vars (CORS, Redis, etc.)

### 1.3 Ingestion Domain (fixes BUG-02, ARCH-01)

- [ ] Write failing test: `test_fingerprint_consistency.py` (canonical fingerprint)
- [ ] Implement `ingestion/service.py` — unified `generate_fingerprint()` function
- [ ] Write failing test: `test_import_endpoint.py` (full import flow)
- [ ] Implement `ingestion/router.py` — absorb Next.js `/api/import` logic
- [ ] Implement `ingestion/schemas.py` — Pydantic models (fixes IMP-04)
- [ ] Run tests, verify pass

### 1.4 Categorization Domain (fixes BUG-03, BUG-04, ARCH-04)

- [ ] Write failing test: `test_singleton_classifier.py` (HypCD init once)
- [ ] Implement singleton HypCD classifier via FastAPI lifespan
- [ ] Write failing test: `test_classify_single.py` (no endpoint conflict)
- [ ] Implement `categorization/router.py` — single `/classify` endpoint
- [ ] Write failing test: `test_classify_batch.py` (in-process, no N+1 Celery)
- [ ] Implement batch classify in-process
- [ ] Migrate existing tests from `apps/api/tests/test_classify*.py`
- [ ] Run tests, verify pass

### 1.5 Forecasting Domain (fixes BUG-07)

- [ ] Write failing test: `test_forecast_preserves_metadata.py`
- [ ] Implement `forecasting/router.py` — migrate from `forecast.py`
- [ ] Migrate existing `test_forecast.py`
- [ ] Run tests, verify pass

### 1.6 Training Domain (fixes BUG-01)

- [ ] Write failing test: `test_training_status_update.py` (Celery updates DB)
- [ ] Modify `tasks/training_tasks.py` — add service-role Supabase client
- [ ] Implement `training/router.py` — migrate from `training.py`
- [ ] Run tests, verify pass

### 1.7 Accounts Domain

- [ ] Implement `accounts/router.py` — `GET /transactions`, `GET /profile`
- [ ] Write test for transaction listing with auth

### 1.8 Main App Update (fixes ARCH-03, ARCH-05)

- [ ] Update `main.py` — register domain routers, add error handler middleware
- [ ] Fix CORS: read `ALLOWED_ORIGINS` from env var
- [ ] Remove `google-generativeai` from `requirements.txt`
- [ ] Add `structlog` to `requirements.txt`
- [ ] Run full test suite

### 1.9 Frontend Cleanup

- [ ] Delete `apps/web/app/api/import/route.ts`
- [ ] Delete `apps/web/app/api/decrypt-xlsx/` directory
- [ ] Delete `apps/web/app/api/ingest/` directory
- [ ] Delete `apps/web/app/api/transactions/` directory
- [ ] Create `apps/web/lib/api/client.ts` — centralized API client
- [ ] Update all components to use new API client
- [ ] Run frontend tests, verify pass

### 1.10 Worker Fix

- [ ] Modify `training_tasks.py` — service-role client, DB status updates
- [ ] Test: start training job, verify DB status changes to `completed`

### 1.11 Recheck Fixes (Missed Items)

- [ ] Rewrite `CLAUDE.md` to reflect new architecture (fixes IMP-03)
- [ ] Create Supabase migration for `uploaded_files` table (missing from schema)
- [ ] Standardize `type` column values (`credit`/`debit` only, not `expense`/`income`)
- [ ] Move `anchors.pt` and `hypcd_model.pt` to `models/` directory
- [ ] Delete or repurpose `apps/web/proxy.ts` if it proxies to old routes
- [ ] Consolidate root `requirements.txt` vs `apps/api/requirements.txt`

---

## Milestone 2: API Design, OpenAPI & Database Optimization

### 2.1 API Design

- [ ] Create `core/pagination.py` — cursor-based (keyset) pagination, no OFFSET
- [ ] Create `core/filtering.py` — query param filtering (date range, amount, category, merchant)
- [ ] Add comprehensive OpenAPI examples/descriptions to all schemas
- [ ] Implement versioning support (`/api/v1` prefix management)
- [ ] Write tests for pagination and filtering

### 2.2 Database Optimization

- [ ] Run diagnostic queries (`pg_stat_statements`, cache hit ratio, seq scan audit)
- [ ] Add missing indexes: `idx_transactions_user_merchant`, `idx_transactions_pagination`, `idx_transactions_user_amount`
- [ ] Add GIN index on `raw_data` JSONB column
- [ ] Implement batch upsert for imports (single INSERT for 1000 rows)
- [ ] Configure autovacuum for transactions table (5% threshold)
- [ ] Create Supabase migration for `uploaded_files` table
- [ ] Write tests for keyset pagination queries

## Milestone 3: Security Hardening

- [ ] Create `core/rate_limiter.py` — Redis sliding window (fixes BUG-05)
- [ ] Create `core/security_headers.py` — Helmet-equivalent (X-Frame, HSTS, CSP)
- [ ] Update `core/auth.py` — RBAC preparation, token expiry validation
- [ ] Update CORS config for production domains (explicit allowlist)
- [ ] Add request size limits to prevent DoS
- [ ] Write security tests (CORS, rate limit, auth bypass, security headers)

## Milestone 4: DevOps & CI/CD

- [ ] Create multi-stage `Dockerfile` (separate API and Worker targets)
- [ ] Create `.dockerignore` (exclude `.git`, `node_modules`, `.venv`, `.next`, `__pycache__`, `apps/web/`)
- [ ] Update `docker-compose.yml` — separate build targets, env_file, resource limits
- [ ] Create `.github/workflows/ci.yml` — lint (ruff+eslint) → security (bandit+pip-audit+gitleaks) → test (pytest+vitest) → build (Docker+Trivy)
- [ ] Create `.github/workflows/deploy.yml` — staging (auto) → production (manual gate)
- [ ] Update `.env.example` with all required vars and descriptions
- [ ] Set up Supabase CLI migrations (fixes IMP-01)
- [ ] Add Flower dashboard auth (basic auth or restrict to internal)

## Milestone 5: Monitoring & Observability

- [ ] Create `core/middleware/request_id.py` — UUID per request, attached to all logs
- [ ] Create `core/middleware/request_logging.py` — structlog with duration, status, user_id
- [ ] Integrate Sentry in `main.py` (errors + performance, `send_default_pii=False`)
- [ ] Create `/health` (liveness) and `/ready` (readiness) endpoints (fixes IMP-05)
- [ ] Structured logging across all domains (replace all `print()` statements)
- [ ] Write monitoring tests (health check behavior, request ID propagation)
- [ ] Set up alerting: API down, error rate > 5%, p95 > 2s

## Milestone 6: SRE Foundation (Phase 2)

- [ ] Define SLI/SLO metrics with error budget policy
- [ ] Create runbooks for common failures (API 503, stuck training jobs, Redis down)
- [ ] Set up performance testing with k6 (load test script, CI integration)
- [ ] Plan chaos engineering experiments (kill container, slow DB, Redis disconnect)
- [ ] Implement toil reduction automation (auto-cleanup old checkpoints, stale jobs)
