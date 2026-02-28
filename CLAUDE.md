# CLAUDE.md

This file provides guidance to AI agents working with this repository.

## Project Overview

SCALE is a personal finance intelligence platform. It combines a Next.js 16 frontend (App Router, Supabase Auth) with a FastAPI backend (ML inference, forecasting, async training). Auth is Google OAuth via Supabase.

## Architecture (Post-M1 Restructure)

### Monorepo Structure

```
apps/
  web/           → Next.js 16 frontend (App Router, Tailwind, Supabase Auth)
  api/           → FastAPI backend (ML, ingestion, forecasting)
    core/        → Infrastructure: config, auth, errors, logging
    domains/     → 6 domain modules (see below)
    routers/     → Legacy (only health.py remains)
    tasks/       → Celery async tasks
packages/
  categorization/  → HypCD classifier model + training pipeline
  forecasting/     → TFT time-series forecasting
  ingestion_engine/ → CSV/Excel parser
models/            → Pretrained model files (anchors.pt, hypcd_model.pt)
architecture/      → System design docs
```

### Domain Modules (`apps/api/domains/`)

| Domain           | Endpoints                                                                 | Purpose                                  |
| ---------------- | ------------------------------------------------------------------------- | ---------------------------------------- |
| `ingestion`      | `POST /ingest/csv`                                                        | CSV upload, parse, fingerprint, classify |
| `categorization` | `/classify`, `/classify/batch`, `/feedback`, `/discover`, `/models`       | ML classification                        |
| `forecasting`    | `/forecast/predict`, `/forecast/safe-to-spend`                            | Spending predictions                     |
| `training`       | `/training/upload`, `/train`, `/training/status/{id}`, `/training/latest` | Model training                           |
| `anomaly`        | `/anomaly/alerts/{user_id}`                                               | Anomaly detection (stub)                 |
| `accounts`       | `/accounts/transactions`, `/accounts/profile`                             | User data access                         |

### Core Infrastructure (`apps/api/core/`)

- `config.py` — Pydantic Settings (env vars)
- `auth.py` — JWT validation, get_user_client(), get_service_client()
- `errors.py` — RFC 7807 error handler
- `logging.py` — structlog (JSON prod, console dev)

## Development Commands

```bash
# Frontend
cd apps/web && npm install && npm run dev    # http://localhost:3000

# Backend API
cd apps/api
source ../../.venv/bin/activate
uvicorn apps.api.main:app --reload --port 8000

# Tests
python -m pytest apps/api/ -v --tb=short

# Domain-specific tests
python -m pytest apps/api/domains/ingestion/tests/ -v
python -m pytest apps/api/domains/categorization/tests/ -v
```

## Environment Variables

### Backend (`apps/api/.env`)

```bash
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_KEY=eyJ...       # For Celery workers
ALLOWED_ORIGINS=http://localhost:3000,https://your-domain.com
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### Frontend (`apps/web/.env.local`)

```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

## Key Design Decisions

### Fingerprinting

All transaction deduplication uses a **6-field SHA256** fingerprint:
`SHA256(DATE|AMOUNT|MERCHANT|DESCRIPTION|PAYMENT_METHOD|REFERENCE)` (uppercased)
Canonical implementation: `apps/api/domains/ingestion/service.py:generate_fingerprint()`

### Authentication

- Frontend: Supabase Auth (Google OAuth), JWT in `Authorization: Bearer` header
- Backend: `core/auth.py` validates JWT, creates Supabase client scoped to user (RLS)
- Celery workers: Use `get_service_client()` with service-role key (bypasses RLS)

### Error Handling

All API errors return RFC 7807 Problem Details format:

```json
{
  "type": "validation_error",
  "title": "Validation Error",
  "status": 422,
  "detail": "..."
}
```

### Frontend API Client

All backend calls go through `apps/web/lib/api/client.ts` — centralized fetch wrapper with auth token injection. The Next.js API routes have been deleted.

## Database

- **Supabase/Postgres** with RLS enabled
- `transactions` table: user_id, amount, description, merchant_name, category, fingerprint, raw_data (JSONB)
- `training_jobs` table: status tracking for async training
- `uploaded_files` table: deduplication by file hash

## Testing

51 tests across core + 6 domain modules. TDD workflow (red-green-refactor).

```bash
python -m pytest apps/api/ -v
```
