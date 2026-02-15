# HpyCD Training Pipeline & Localhost Deployment Design

**Date:** 2026-02-15  
**Status:** Awaiting Approval  
**Scope:** Complete training pipeline finalization + localhost deployment infrastructure

---

## Executive Summary

Implement a production-ready localhost deployment for the HpyCD (Hyperbolic Categorization Decision) training pipeline with containerized services, async job processing, and health monitoring.

---

## Current State Analysis

### What's Already Implemented ✅

- `packages/categorization/training_pipeline.py` - 777-line comprehensive pipeline
- `HypCDClassifier` with hyperbolic projection (Bert-768 → 256 → 128)
- FastAPI app with training endpoints at `/api/v1/train`
- Checkpoint management with resume capability
- Hierarchical loss function
- Training monitoring and metrics
- Health check router exists

### What's Missing ❌

1. **Containerization** - No Docker or docker-compose
2. **Async Architecture** - Training runs synchronously (blocks API)
3. **Job Queue** - No Redis/Celery for background tasks
4. **Inference Endpoint** - No way to use trained models
5. **Local Dev Environment** - No `.env.local` or startup scripts

---

## Proposed Approaches

### Approach A: Docker Compose + Celery Workers (Recommended)

**Architecture:**

```
┌─────────────────┐     ┌─────────────┐     ┌─────────────────┐
│   API (FastAPI) │────▶│    Redis    │◀────│ Celery Worker   │
│    Port 8000    │     │   Port 6379 │     │  (Training Jobs)│
└─────────────────┘     └─────────────┘     └─────────────────┘
         │                                              │
         ▼                                              ▼
┌─────────────────┐                          ┌─────────────────┐
│  Supabase DB    │                          │  Model Storage  │
└─────────────────┘                          └─────────────────┘
```

**Components:**

1. **API Service** - FastAPI container (port 8000)
2. **Redis** - Job queue and result backend (port 6379)
3. **Worker** - Celery worker for background training
4. **Flower** - Optional: Celery monitoring UI (port 5555)

**Pros:**

- True async training (API stays responsive)
- Production-like architecture
- Scalable (add more workers)
- Training survives API restarts

**Cons:**

- More complex initial setup
- Requires Redis service

---

### Approach B: Single Container + BackgroundTasks

**Architecture:** Single Docker container using FastAPI `BackgroundTasks` for training.

**Pros:**

- Simpler setup (one container)
- No additional services
- Good for local development

**Cons:**

- Training shares resources with API
- No persistence if container restarts
- Not production-ready

---

### Approach C: Pure Local (No Docker)

**Architecture:** Enhanced local Python setup.

**Pros:**

- Fastest iteration
- No Docker overhead
- Direct debugging

**Cons:**

- "Works on my machine" risk
- No isolation
- Manual dependency management

---

## Recommended: Approach A

Rationale: The training pipeline takes minutes to run (BERT embeddings + hyperbolic training). Blocking the API during this time is unacceptable for a production system. Docker Compose provides the right abstraction for local development that mirrors production.

---

## Design Details

### 1. Container Architecture

**Services:**

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| api | python:3.11-slim | 8000 | FastAPI application |
| redis | redis:7-alpine | 6379 | Job queue & results |
| worker | (same as api) | - | Celery training worker |
| flower | mher/flower | 5555 | Monitoring UI |

### 2. Data Flow

**Training Job Flow:**

1. Client POST `/api/v1/train` → API receives request
2. API enqueues job in Redis → Returns job_id immediately
3. Celery worker picks up job → Runs `training_pipeline.py`
4. Worker updates Supabase `training_jobs` table with progress
5. Client polls GET `/api/v1/training/status/{job_id}`

**Inference Flow:**

1. Client POST `/api/v1/classify` with transaction description
2. API loads latest trained model from storage
3. Returns predicted category with confidence score

### 3. File Structure

```
SCALE APP/
├── docker-compose.yml           # NEW: Orchestration
├── Dockerfile                   # NEW: API/Worker image
├── .env.local                   # NEW: Local environment
├── scripts/
│   └── start-local.sh           # NEW: Convenience startup
├── apps/
│   └── api/
│       ├── main.py              # EXISTING (enhanced)
│       ├── celery_app.py        # NEW: Celery configuration
│       └── routers/
│           ├── training.py      # EXISTING (modified for async)
│           └── classify.py      # NEW: Model inference
├── packages/
│   └── categorization/
│       └── training_pipeline.py # EXISTING
```

### 4. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/train` | Start training job (async) |
| GET | `/api/v1/training/status/{job_id}` | Get job status |
| GET | `/api/v1/training/latest` | Get latest job |
| POST | `/api/v1/classify` | Classify transaction |
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/models` | List available models |

### 5. Environment Configuration

**`.env.local`:**

```bash
# API Configuration
API_PORT=8000
API_HOST=0.0.0.0

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Supabase Configuration
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# Training Configuration
MODEL_CHECKPOINT_DIR=/app/checkpoints
DEFAULT_EPOCHS=50
DEFAULT_BATCH_SIZE=32

# Worker Configuration
CELERY_WORKERS=2
CELERY_LOG_LEVEL=INFO
```

### 6. Model Persistence Strategy

- Checkpoints saved to `/app/checkpoints/` (Docker volume)
- Latest model symlink: `checkpoints/latest_model.pt`
- Best model symlink: `checkpoints/best_model.pt`
- Model metadata stored in Supabase `trained_models` table

### 7. Health Monitoring

**Health Checks:**

- API: `GET /api/v1/health` - Returns 200 with status
- Redis: Celery built-in ping
- Worker: Celery worker inspect
- Database: Supabase connection test

**Metrics:**

- Training jobs queued/running/completed
- Average training time per job
- Model accuracy over time
- API request latency

### 8. Testing Strategy

| Test Type | Coverage |
|-----------|----------|
| Unit | Training pipeline components |
| Integration | API endpoints with mock DB |
| E2E | Full training flow via docker-compose |
| Load | Concurrent training jobs |

---

## Implementation Phases

### Phase 1: Containerization (Priority 1)

- Create `Dockerfile` with Python 3.11
- Create `docker-compose.yml` with Redis
- Add `.env.local` template
- Test basic API startup

### Phase 2: Async Training (Priority 1)

- Add Celery to requirements
- Create `celery_app.py` configuration
- Modify `/train` endpoint to use async tasks
- Implement job status tracking

### Phase 3: Inference Endpoint (Priority 2)

- Create `/classify` router
- Implement model loading from checkpoints
- Add prediction caching

### Phase 4: Monitoring (Priority 3)

- Add Flower for Celery monitoring
- Enhanced health checks
- Basic metrics endpoint

### Phase 5: Documentation (Priority 3)

- README with setup instructions
- API documentation
- Troubleshooting guide

---

## Open Questions

1. **GPU Support:** Should worker container have GPU access for CUDA training?
2. **Model Versioning:** How many model versions to keep? (suggest: last 5)
3. **Auto-scaling:** Should workers auto-scale based on queue depth?

---

## Approval

**Design Status:** ⏳ Awaiting Approval

Please confirm:

1. [ ] Approve Approach A (Docker Compose + Celery)
2. [ ] Include inference endpoints (`/classify`)
3. [ ] Any specific port requirements?

Once approved, I will proceed to the **writing-plans** phase to create the detailed implementation plan.
