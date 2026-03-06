# SCALE App — System Design Document

## 1. Non-Functional Requirements

| Category         | Metric                 | Phase 1 (Prototype) | Phase 2 (Growth)        | Phase 3 (Scale)          |
| ---------------- | ---------------------- | ------------------- | ----------------------- | ------------------------ |
| **Performance**  | API response (p95)     | < 500ms             | < 200ms                 | < 100ms                  |
|                  | Page load time         | < 3s                | < 2s                    | < 1s                     |
|                  | DB query time          | < 100ms             | < 50ms                  | < 10ms                   |
|                  | Batch import (1K rows) | < 10s               | < 5s                    | < 2s                     |
| **Scalability**  | Concurrent users       | 100                 | 1,000                   | 10,000+                  |
|                  | Requests per second    | 10                  | 100                     | 1,000+                   |
|                  | Data volume            | < 1GB               | < 50GB                  | < 1TB                    |
| **Availability** | Uptime target          | 99% (3.6 days down) | 99.9% (8.7 hrs)         | 99.99% (52 min)          |
|                  | RPO (data loss)        | 24 hours            | 1 hour                  | 0 (real-time)            |
|                  | RTO (recovery)         | 24 hours            | 4 hours                 | 1 hour                   |
| **Security**     | Auth                   | Supabase JWT        | JWT + RBAC              | JWT + RBAC + MFA         |
|                  | Encryption             | TLS in transit      | TLS + encrypted at rest | + E2E for FL             |
|                  | Compliance             | Basic privacy       | GDPR-aware              | Full GDPR + AA framework |
| **Cost**         | Monthly infra          | $0 (free tiers)     | $50-100                 | $500+ (GPU nodes)        |

---

## 2. Request Lifecycle

Every request through the system follows this path:

```
Client Request
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│ 1. TLS TERMINATION (Vercel/Railway/Cloud Run)           │
│    • HTTPS enforced, HTTP → HTTPS redirect              │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 2. REVERSE PROXY / LOAD BALANCER                        │
│    • Phase 1: Railway built-in (single instance)        │
│    • Phase 2: Cloud Run auto-scaler (0→N instances)     │
│    • Phase 3: K8s Ingress Controller (NGINX/Traefik)    │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│ 3. FASTAPI MIDDLEWARE CHAIN (order matters)              │
│                                                         │
│    ┌──────────────┐                                     │
│    │ Request ID   │ Generate UUID, attach to context     │
│    └──────┬───────┘                                     │
│    ┌──────▼───────┐                                     │
│    │ CORS         │ Validate origin against allowlist    │
│    └──────┬───────┘                                     │
│    ┌──────▼───────┐                                     │
│    │ Rate Limiter │ Redis sliding window (per user/IP)   │
│    └──────┬───────┘                                     │
│    ┌──────▼───────┐                                     │
│    │ Auth         │ Validate JWT, extract user_id        │
│    └──────┬───────┘                                     │
│    ┌──────▼───────┐                                     │
│    │ Logging      │ Log request start (structlog)        │
│    └──────┬───────┘                                     │
└───────────┼─────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────┐
│ 4. DOMAIN ROUTER                                        │
│    • Input validation (Pydantic schemas)                │
│    • Business logic (service layer)                     │
│    • Database operations (Supabase client)              │
│    • Response serialization                             │
└───────────┬─────────────────────────────────────────────┘
            ▼
┌─────────────────────────────────────────────────────────┐
│ 5. RESPONSE PIPELINE                                    │
│    • Structured response with request_id                │
│    • Security headers (X-Content-Type-Options, etc.)    │
│    • Access logging (duration, status, user_id)         │
│    • Error wrapping (RFC 7807 if error)                 │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Load Balancing Strategy

### Phase 1: No Load Balancer (Single Instance)

```
Client → Railway/Render (single container) → FastAPI (Uvicorn, 1 worker)
```

- **Why**: Free tier = single instance. Uvicorn handles concurrency via async.
- **Capacity**: ~50-100 concurrent requests (sufficient for < 100 users).
- **Failure mode**: Container crash → Railway auto-restarts (30s downtime).

### Phase 2: Platform-Managed Auto-Scaling

```
Client → Cloud Run Load Balancer → Instance 1 (Uvicorn)
                                 → Instance 2 (Uvicorn)
                                 → Instance N (auto-scaled)
```

- Cloud Run scales from 0 to N based on request queue depth.
- **Sticky sessions**: Not needed — API is stateless (JWT auth, no server sessions).
- **Health checks**: `/api/v1/health` endpoint, 10s interval.
- **Cold start mitigation**: Keep min-instances=1 in production.
- **Capacity**: ~1,000 concurrent requests.

### Phase 3: Kubernetes Ingress + Service Mesh

```
Client → K8s Ingress Controller (NGINX) → Service (ClusterIP)
                                         → Pod 1 (Uvicorn, 4 workers)
                                         → Pod 2 (Uvicorn, 4 workers)
                                         → Pod N (HPA auto-scaled)
```

- **Algorithm**: Round-robin (stateless API) or least-connections for ML endpoints.
- **HPA**: Horizontal Pod Autoscaler targets 70% CPU or custom metrics (request queue depth).
- **GPU routing**: ML-heavy endpoints (`/classify/batch`, `/forecast`) routed to GPU node pool.
- **Capacity**: 10,000+ concurrent requests.

---

## 4. Caching Architecture

### Layer 1: Client-Side Cache (Browser/Mobile)

| Data              | Strategy                 | TTL | Invalidation              |
| ----------------- | ------------------------ | --- | ------------------------- |
| Transaction list  | `stale-while-revalidate` | 60s | On import/new transaction |
| Categories        | `cache-first`            | 24h | Manual refresh            |
| User profile      | `cache-first`            | 1h  | On settings update        |
| Model predictions | `no-cache`               | n/a | Always fresh              |

Implementation: HTTP `Cache-Control` headers set by FastAPI responses.

### Layer 2: CDN/Edge Cache (Vercel)

| Resource                        | Cached | TTL                       |
| ------------------------------- | ------ | ------------------------- |
| Static assets (JS, CSS, images) | ✅     | 1 year (hashed filenames) |
| API responses                   | ❌     | Never (personalized data) |
| OpenAPI spec (`/docs`)          | ✅     | 1 hour                    |

### Layer 3: Application Cache (Redis/Upstash)

| Data                   | Key Pattern             | TTL             | Purpose                         |
| ---------------------- | ----------------------- | --------------- | ------------------------------- |
| User's category list   | `cat:{user_id}`         | 1h              | Avoid DB query on each classify |
| HypCD model embeddings | `emb:{model_version}`   | Until new model | Preloaded on startup            |
| Rate limit windows     | `rl:{user_id}:{window}` | 60s             | Sliding window counters         |
| Training job status    | `job:{job_id}`          | Until completed | Reduce DB polls                 |
| Session/auth tokens    | NOT cached              | n/a             | JWT is stateless                |

### Layer 4: Database Query Cache (Supabase/Postgres)

- **Connection pooling**: Supabase uses PgBouncer (built-in). Transaction mode for API, Session mode for workers.
- **Prepared statements**: Supabase client uses parameterized queries automatically.
- **Materialized views** (Phase 2+): For expensive dashboard aggregations (monthly spend, category breakdown).

---

## 5. Database Design

### Current Schema (2 tables)

```
transactions              training_jobs
├── id (UUID PK)          ├── id (UUID PK)
├── user_id (FK→auth)     ├── user_id (FK→auth)
├── transaction_date      ├── status (pending/processing/completed/failed)
├── amount (decimal)      ├── model_type
├── currency              ├── metrics (JSONB)
├── description           ├── checkpoint_path
├── merchant_name         ├── created_at
├── category              └── updated_at
├── payment_method
├── status
├── fingerprint (UNIQUE per user)
├── raw_data (JSONB)
└── created_at
```

### Missing Table: `uploaded_files`

The Next.js import route references this table but it's **not in the schema files**:

```sql
uploaded_files
├── id (UUID PK)
├── user_id (FK→auth)
├── file_hash (TEXT)
├── filename (TEXT)
├── upload_type (TEXT)
└── created_at
```

> [!WARNING]
> This table needs to be created via Supabase migration. It's referenced in code but missing from the schema documentation.

### Index Strategy

| Index                               | Purpose                                        | Type                             |
| ----------------------------------- | ---------------------------------------------- | -------------------------------- |
| `idx_transactions_user_date`        | Dashboard queries (user's recent transactions) | B-tree composite                 |
| `idx_transactions_category`         | Category filtering                             | B-tree                           |
| `idx_transactions_user_fingerprint` | Dedup on import (UNIQUE)                       | B-tree unique                    |
| `idx_training_jobs_pending`         | Worker polling for pending jobs                | Partial (WHERE status='pending') |
| `idx_training_jobs_user_status`     | User's latest training job                     | B-tree composite                 |

**Phase 2+ additions:**

- `idx_transactions_merchant` — For merchant-based queries
- `idx_transactions_amount_range` — For amount filtering
- GIN index on `raw_data` — For JSONB queries

### Connection Pooling

| Phase   | Pooler                        | Mode                                  | Max Connections |
| ------- | ----------------------------- | ------------------------------------- | --------------- |
| Phase 1 | Supabase built-in (PgBouncer) | Transaction                           | 20 (free tier)  |
| Phase 2 | Supabase Pro PgBouncer        | Transaction                           | 200             |
| Phase 3 | Self-hosted PgBouncer + Citus | Session (workers) / Transaction (API) | 1000+           |

### Row Level Security (RLS)

Already implemented for `transactions` and `training_jobs`:

- Users can only SELECT/INSERT/UPDATE/DELETE their own data via `auth.uid() = user_id`.
- Celery worker uses `service_role` key to bypass RLS for status updates.

### Future: Polyglot Persistence

```
Phase 1 (Now)          Phase 2              Phase 3
┌───────────┐     ┌───────────┐       ┌───────────┐
│ Supabase  │     │ Supabase  │       │   Citus   │ ← Sharded OLTP
│ (Postgres)│     │ (Postgres)│       │ (Postgres)│
│ ALL DATA  │     │ OLTP      │       └───────────┘
└───────────┘     └─────┬─────┘       ┌───────────┐
                        │CDC          │ClickHouse │ ← OLAP Analytics
                  ┌─────▼─────┐       └───────────┘
                  │ Upstash   │       ┌───────────┐
                  │ (Redis)   │       │  Qdrant   │ ← Vector Search
                  └───────────┘       └───────────┘
```

---

## 6. Queue & Worker Architecture

### Current Design

```
FastAPI → Redis (Celery broker) → Worker (2 replicas)
                                  └─ training queue
```

### Improved Design (Phase 1)

```
FastAPI
  │
  ├── Sync operations (< 1s): Direct in-process
  │   • Single classify
  │   • Transaction lookup
  │   • Health check
  │
  └── Async operations (> 1s): Celery queue
      ├── training queue → Worker replicas
      │   • Model training (heavy compute)
      │   • Batch retraining
      │
      └── inference queue → Worker replicas (Phase 2)
          • Batch classification (100+ items)
          • Forecast generation
          • TDA anomaly analysis
```

### Task Priority & Routing

| Task                      | Queue       | Priority | Timeout | Retries |
| ------------------------- | ----------- | -------- | ------- | ------- |
| Model training            | `training`  | Low      | 30min   | 1       |
| Batch classify            | `inference` | High     | 5min    | 2       |
| Forecast generation       | `inference` | Medium   | 10min   | 2       |
| Gradient aggregation (FL) | `fl`        | Low      | 15min   | 1       |

### Result Delivery

```
Client polls: GET /training/status/{job_id}
  │
  ├── Check Redis cache first → fast path (< 5ms)
  │
  └── Fallback to DB query → slow path (< 50ms)

Phase 2: Replace polling with SSE push
  Worker completes → Redis pub/sub → SSE channel → Client
```

---

## 7. Failure Modes & Recovery

| Failure                            | Impact                                      | Detection                  | Recovery                                      | RTO       |
| ---------------------------------- | ------------------------------------------- | -------------------------- | --------------------------------------------- | --------- |
| **API container crash**            | All requests fail                           | Health check failure       | Platform auto-restart                         | 30s       |
| **Worker crash**                   | Async tasks stall                           | Celery heartbeat           | Auto-restart + task retry                     | 60s       |
| **Redis down**                     | Rate limits reset, cache miss, queue stalls | Redis health check         | Upstash auto-recovery / fallback to in-memory | 5s-2min   |
| **Supabase down**                  | All data ops fail                           | DB health check            | Supabase SLA recovery                         | 5-30min   |
| **Supabase connection exhaustion** | New requests rejected                       | Connection pool monitoring | PgBouncer auto-recycles                       | 10s       |
| **HypCD model corrupt/missing**    | Classification fails                        | Startup health check       | Return graceful error, fallback to rule-based | Immediate |
| **Training job fails**             | User's model not updated                    | Celery error handler       | Status → "failed" in DB, user notified        | Immediate |
| **Network partition (API↔Redis)**  | Rate limits bypass, cache miss              | Redis ping timeout         | API continues without cache (degraded)        | Automatic |
| **Disk full (checkpoints)**        | Training can't save models                  | Disk usage monitoring      | Alert + cleanup old checkpoints               | Manual    |

### Circuit Breaker Pattern (Phase 2+)

For external service calls (AA framework, Stripe, future APIs):

```python
# Pseudocode
@circuit_breaker(failure_threshold=5, recovery_timeout=30)
async def call_external_service():
    ...  # If 5 failures in a row, stop trying for 30s
```

### Graceful Degradation Hierarchy

```
Full service → Cache miss (slower) → DB degraded (errors)
                                     → Worker down (no async)
                                     → Redis down (no rate limit)
                                     → Total failure (maintenance page)
```

---

## 8. Scaling Strategy

### Phase 1: Vertical Scaling (Free Tier)

```
Single FastAPI instance
  • Uvicorn with 1 worker (Railway/Render constraint)
  • Async handlers for I/O concurrency
  • In-process inference for single classify
  • Celery for heavy compute (uses same container image)
```

**Bottleneck**: CPU for ML inference. Single worker can't parallelize PyTorch.

### Phase 2: Horizontal Scaling (Cloud Run)

```
Cloud Run auto-scales FastAPI instances (0→10)
  • Each instance: Uvicorn with 2-4 workers
  • Stateless: no in-memory state between requests
  • Shared state: Redis (Upstash) for cache/queue
  • Shared storage: Supabase for data
  • Separate worker service for heavy compute
```

**Bottleneck**: Single Supabase Postgres (connection limit ~200).

### Phase 3: Distributed Scaling (Kubernetes)

```
K8s cluster with node pools:
  • Standard nodes: API pods (HPA, 2-20 replicas)
  • GPU nodes: Ray Serve pods (TFT, HypCD inference)
  • Worker nodes: Celery pods (training tasks)

Database:
  • Citus (sharded by user_id) for OLTP
  • ClickHouse for analytics
  • Qdrant for vector search
```

**Bottleneck**: Cross-shard queries, distributed transaction coordination.

---

## 9. Data Consistency Model

| Operation               | Consistency             | Rationale                           |
| ----------------------- | ----------------------- | ----------------------------------- |
| Transaction insert      | **Strong** (ACID)       | Financial data must be correct      |
| Balance read            | **Strong** (latest)     | User sees accurate balance          |
| Category update         | **Eventual** (~1s)      | Category cache refreshes async      |
| Training status         | **Eventual** (~5s)      | Polling interval controls freshness |
| Forecast prediction     | **Eventual** (~minutes) | Model updates are periodic          |
| Dashboard aggregations  | **Eventual** (~1min)    | Pre-computed, cache refreshed       |
| FL gradient aggregation | **Eventual** (~hours)   | Batch aggregation cycle             |

### Conflict Resolution

- **Duplicate imports**: Fingerprint uniqueness constraint → DB rejects, API returns `skipped_duplicates` count.
- **Concurrent model training**: Lock per `user_id` in Redis → Only one training job per user at a time.
- **Category corrections**: Last-write-wins → User's manual correction always overrides model prediction.

---

## 10. Auth & Session Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Auth Flow (Supabase)                  │
│                                                       │
│  Client                 Supabase                API   │
│    │                      │                      │    │
│    │── Login (Google) ───►│                      │    │
│    │◄── JWT (access +  ──│                      │    │
│    │    refresh token)    │                      │    │
│    │                      │                      │    │
│    │─── API call ─────────┼──── Bearer JWT ─────►│    │
│    │                      │                      │    │
│    │                      │    Validate JWT ◄────│    │
│    │                      │    Extract user_id   │    │
│    │                      │    Check expiry      │    │
│    │                      │────── OK ───────────►│    │
│    │                      │                      │    │
│    │◄─── Response ────────┼──────────────────────│    │
└─────────────────────────────────────────────────────┘
```

**Key decisions:**

- **No server sessions** — JWT is self-contained, API is fully stateless.
- **Token refresh** — Client handles refresh via Supabase SDK. Backend never refreshes tokens.
- **Service-role key** — Used only by Celery worker (bypasses RLS for status updates).
- **Mobile auth** — Same JWT flow via Supabase mobile SDK (React Native / Flutter).

---

## 11. CDN & Edge Strategy

| Asset                     | Served From                        | Cache                   |
| ------------------------- | ---------------------------------- | ----------------------- |
| Next.js UI (HTML/JS/CSS)  | Vercel Edge Network                | global CDN, ISR         |
| Static images/fonts       | Vercel CDN                         | 1 year (immutable hash) |
| API responses             | FastAPI origin (Railway/Cloud Run) | NOT cached at edge      |
| OpenAPI docs `/docs`      | FastAPI                            | Could be CDN-cached     |
| ML model weights (for FL) | Cloud Storage (GCS/S3)             | CDN with versioned URLs |

**Phase 2+**: Consider Cloudflare or Vercel's Edge Middleware for:

- Geographic routing (serve API from closest region)
- DDoS protection (free tier available)
- Bot detection before requests hit API

---

## 12. SSE Streaming Design

For real-time updates (training progress, AI agent thoughts):

```
┌──────────┐        ┌──────────────┐        ┌──────────┐
│  Client  │──GET──►│  FastAPI     │◄──SUB──│  Redis   │
│  (SSE)   │◄─event─│  SSE Handler │        │  Pub/Sub │
└──────────┘        └──────────────┘        └────┬─────┘
                                                  │ PUB
                                            ┌─────┴─────┐
                                            │  Worker   │
                                            │(publishes │
                                            │ progress) │
                                            └───────────┘
```

### Protocol Detail

```
Client: GET /api/v1/training/stream/{job_id}
Accept: text/event-stream

Server:
  event: progress
  data: {"step": 42, "total": 100, "loss": 0.032, "status": "training"}

  event: progress
  data: {"step": 43, "total": 100, "loss": 0.029, "status": "training"}

  event: complete
  data: {"status": "completed", "metrics": {"accuracy": 0.94}}
```

### Connection Management

- **Timeout**: 5 minutes idle, client auto-reconnects with `Last-Event-ID`.
- **Backpressure**: If Redis pub/sub buffer fills, drop oldest messages (progress is idempotent).
- **Scaling**: Each API instance subscribes independently. No sticky sessions needed.

---

## 13. Federated Learning Protocol Design

```
┌───────────────────────────────────────────────────────┐
│              FL Round (every N hours)                   │
│                                                        │
│  1. Server → Clients: "Download global model v42"      │
│     Protocol: gRPC (binary Protobuf, model weights)    │
│     Storage: Cloud Storage signed URL                   │
│                                                        │
│  2. Client: Local training on device                   │
│     Runtime: CoreML (iOS) / TFLite (Android) /         │
│              TF.js (Web Worker)                         │
│     Data: User's transaction history (NEVER leaves)    │
│     Epochs: 1-3 (lightweight, < 30s)                   │
│                                                        │
│  3. Client → Server: Upload gradient deltas            │
│     Protocol: gRPC (Protobuf, compressed tensors)      │
│     Privacy: Opacus DP noise added BEFORE upload       │
│     Size: ~1-5MB per client per round                  │
│                                                        │
│  4. Server: Secure Aggregation (Flower SecAgg+)        │
│     Minimum clients per round: 10                      │
│     Aggregation: FedAvg or FedProx                     │
│     Result: Global model v43                           │
│                                                        │
│  5. Server → Clients: "New model v43 available"        │
│     Delivery: Push notification → background download  │
└───────────────────────────────────────────────────────┘
```

### Privacy Guarantees

| Layer                         | Mechanism                       | What It Prevents             |
| ----------------------------- | ------------------------------- | ---------------------------- |
| On-device training            | Raw data never leaves           | Direct data exposure         |
| Differential Privacy (Opacus) | Calibrated noise on gradients   | Gradient inversion attacks   |
| Secure Aggregation (SecAgg+)  | Server sees sum, not individual | Server-side snooping         |
| Minimum participation         | ≥10 clients per round           | Small-batch de-anonymization |

---

## 14. Recheck — Missed Items

After thorough review, here's what the implementation plan was missing:

| ID     | Item                                                               | Status                   | Action                                                                                                    |
| ------ | ------------------------------------------------------------------ | ------------------------ | --------------------------------------------------------------------------------------------------------- |
| IMP-01 | No database migration system                                       | ❌ **Missed**            | Add to M4: Supabase CLI migrations (`supabase db diff` + `supabase db push`)                              |
| IMP-03 | CLAUDE.md is stale                                                 | ❌ **Missed**            | Add to M1: Rewrite CLAUDE.md to reflect new architecture                                                  |
| —      | `uploaded_files` table not in schema docs                          | ❌ **Missed**            | Add migration to create table + add to schema docs                                                        |
| —      | Type column (`credit`/`debit` vs `expense`/`income`) inconsistency | ⚠️ **Partially covered** | Standardize in ingestion domain service                                                                   |
| —      | `proxy.ts` in `apps/web/`                                          | ⚠️ **Not analyzed**      | May need deletion if it proxies to old API routes                                                         |
| —      | Flower dashboard (port 5555) needs auth                            | ⚠️ **Not covered**       | Add basic auth or restrict to internal network                                                            |
| —      | `anchors.pt` and `hypcd_model.pt` at project root                  | ⚠️ **Not covered**       | Move to `models/` directory, add to `.gitignore` (large binary files should use Git LFS or cloud storage) |
| —      | No `.dockerignore` file                                            | ❌ **Missed**            | Add to M4: exclude `.git`, `node_modules`, `.venv`, `.next`, etc.                                         |
| —      | `requirements.txt` at root vs `apps/api/requirements.txt`          | ⚠️ **Ambiguous**         | Consolidate — one canonical requirements file                                                             |

> [!IMPORTANT]
> The 3 most impactful misses are: **(1)** Database migration tooling (IMP-01), **(2)** `.dockerignore` (image size blows up without it), and **(3)** Model files at project root (should be in `models/` with Git LFS).
