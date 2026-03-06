# SCALE App — Architecture Brainstorm

## Context

SCALE is an AI-powered financial platform ("AI Accountant") currently built as a tightly-coupled monorepo with Next.js (frontend + server-side API routes) and FastAPI (backend). The codebase has 15 known issues (4 critical bugs, 5 architectural flaws, 6 improvements needed). The vision includes:

- **Mobile app** as the primary interface (future)
- **On-device ML** (HypCD categorization, TFT forecasting) with **federated learning** (gradients to cloud, not raw data)
- **Advanced AI engines**: TDA anomaly detection, Neural RDEs, causal inference (FinCARE), agentic orchestration
- **1M user target** with event-driven architecture
- **Zero-budget start**, future-proof design, progressive investment

---

## Question 1: Is Modular Monolith Still Correct?

### ✅ Verdict: **Yes — with one critical upgrade**

The modular monolith is **absolutely** the right call for where you are today. Here's why:

| Factor           | Microservices                       | Modular Monolith         | Why Monolith Wins (Now)   |
| ---------------- | ----------------------------------- | ------------------------ | ------------------------- |
| Team size        | Needs 2+ devs per service           | 1 dev can own everything | Solo dev reality          |
| Ops overhead     | K8s, service mesh, tracing          | Single deploy            | Zero budget = zero ops    |
| Debug complexity | Distributed tracing required        | Stack trace walks        | Faster iteration          |
| Data consistency | Saga patterns, eventual consistency | Single DB transaction    | Financial data needs ACID |
| Cost             | N containers × N services           | 1 container              | Free tier compatible      |

### The Critical Upgrade: **Domain Modules**

The modular monolith only works if you structure it with **extraction-ready domain boundaries**. This means:

```
apps/api/
├── domains/
│   ├── ingestion/       # Smart Import, file parsing, fingerprinting
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── schemas.py
│   │   └── tests/
│   ├── categorization/  # HypCD, classification
│   ├── forecasting/     # TFT, Neural RDE
│   ├── training/        # Model training, FL aggregation
│   ├── anomaly/         # TDA, Isolation Forest
│   └── accounts/        # User management, auth, settings
├── core/                # Shared: auth, logging, errors, middleware
├── main.py              # Single FastAPI app, registers all domain routers
└── worker.py            # Celery worker, imports domain tasks
```

**Each domain** is a self-contained module with its own router, service layer, schemas, and tests. When you need to extract `forecasting/` into its own service, you:

1. Copy the folder
2. Give it its own `main.py`
3. Replace direct function calls with gRPC/REST calls
4. Done — zero rewriting of business logic

> [!IMPORTANT]
> This is exactly how Shopify, GitHub, and Stripe evolved. They wrote modular monoliths first, then surgically extracted services under load pressure. Not before.

---

## Question 2: Deployment Strategy

### Recommended: **Progressive Free-Tier Stack** (Deploy for $0, migrate for $0)

The key insight: **write code as Docker containers, deploy to free tiers now, migrate to K8s when revenue justifies it**. Docker is the abstraction layer — Railway, Render, Cloud Run, and K8s all speak Docker.

### Phase 1 — Prototype ($0/month)

| Component              | Service                      | Free Tier                                    | Future Migration     |
| ---------------------- | ---------------------------- | -------------------------------------------- | -------------------- |
| **Frontend**           | Vercel                       | 100GB bandwidth, 1M Edge requests            | Stays on Vercel      |
| **Backend (FastAPI)**  | Railway or Render            | 500 hours/mo (Railway) or 750 hours (Render) | → Cloud Run or K8s   |
| **Database**           | Supabase                     | 500MB, 2 projects                            | → Citus/Supabase Pro |
| **Redis**              | Upstash                      | 10K commands/day                             | → Self-hosted Redis  |
| **Worker (Celery)**    | Same Railway instance        | Shares compute                               | → Separate K8s pod   |
| **ML Training**        | Google Colab / Kaggle        | Free GPU (T4)                                | → Modal / Ray        |
| **CI/CD**              | GitHub Actions               | 2,000 min/mo                                 | Stays                |
| **Monitoring**         | Sentry (free) + Upstash Logs | Basic errors + logs                          | → Grafana stack      |
| **Container Registry** | GitHub Container Registry    | Free for public                              | Stays or → ECR       |

### Phase 2 — Growth (~$50-100/month)

When you have users and need reliability:

- Backend → **Cloud Run** (pay-per-request, auto-scale to zero, built-in HTTPS)
- Database → **Supabase Pro** ($25/mo, 8GB, daily backups)
- Redis → **Upstash Pro** ($10/mo)
- Monitoring → **Grafana Cloud free tier** (50GB logs, 10K metrics)

### Phase 3 — Scale (revenue-funded)

When you need GPUs for Ray Serve and dedicated infra:

- Backend → **GKE/EKS** with GPU node pools
- Database → **Citus on Kubernetes** or **Supabase Enterprise**
- ML Serving → **Ray Serve** on GPU nodes
- Full observability → **Self-hosted Grafana + Prometheus + Loki + Tempo**

> [!TIP]
> **The $0 → $50 → $500 migration requires ZERO code changes** if you containerize from day one. The Docker image that runs on Railway runs identically on Cloud Run and K8s.

---

## Proposed Architecture: 3 Approaches

### ⭐ Approach A: Clean Modular Monolith + Docker (Recommended)

**One FastAPI backend, domain-separated, containerized.**

```
┌──────────────────────────────────────────────────┐
│                  CLIENTS                          │
│   Next.js Web App    │    Mobile App (Future)     │
│   (Vercel Edge)      │    (React Native/Flutter)  │
└──────────┬───────────┴──────────┬─────────────────┘
           │ REST + SSE                │ REST + gRPC (gradients)
           ▼                           ▼
┌──────────────────────────────────────────────────┐
│              FastAPI Gateway                      │
│  ┌─────────┐ ┌──────────┐ ┌───────────────┐     │
│  │Ingestion│ │Categorize│ │  Forecasting  │     │
│  │ Domain  │ │ Domain   │ │   Domain      │     │
│  └────┬────┘ └────┬─────┘ └──────┬────────┘     │
│  ┌────┴────┐ ┌────┴─────┐ ┌──────┴────────┐     │
│  │Training │ │ Anomaly  │ │   Accounts    │     │
│  │ Domain  │ │ Domain   │ │   Domain      │     │
│  └─────────┘ └──────────┘ └───────────────┘     │
│                                                   │
│  Core: Auth | Logging | Errors | Rate Limiting    │
└────────────────────┬─────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   ┌─────────┐ ┌─────────┐ ┌──────────┐
   │Supabase │ │ Upstash │ │  Celery  │
   │(Postgres)│ │ (Redis) │ │ Worker   │
   └─────────┘ └─────────┘ └──────────┘
```

**Pros**: Simplest ops, single container, free-tier compatible, all audit bugs fixed  
**Cons**: Single process limits GPU inference (needs worker handoff)  
**Migration**: Each domain folder → its own microservice when needed

---

### Approach B: API Gateway + Separate ML Worker

**Two services from day one: API (FastAPI) + ML Worker (Celery/Ray).**

```
┌──────────────┐  REST/SSE  ┌──────────────┐
│   Clients    │ ──────────►│  FastAPI API  │
└──────────────┘            │  (Domains)   │
                            └──────┬───────┘
                                   │ Redis Queue
                            ┌──────▼───────┐
                            │  ML Worker   │
                            │ (HypCD, TFT) │
                            └──────┬───────┘
                                   │
                            ┌──────▼───────┐
                            │  Supabase DB │
                            └──────────────┘
```

**Pros**: ML doesn't block API, can give worker GPU later  
**Cons**: Two containers to deploy (slightly more cost), coordination overhead  
**Migration**: Worker → Ray Serve cluster, API → API Gateway

---

### Approach C: BFF Pattern (Next.js → FastAPI → Services)

**Keep Next.js as a Backend-For-Frontend that proxies to FastAPI.**

```
┌──────────────┐  ┌─────────────┐  ┌──────────────┐
│   Browser    │──►│  Next.js BFF│──►│  FastAPI     │
└──────────────┘  │  (Proxy)    │  │  (Domains)   │
                  └─────────────┘  └──────────────┘
┌──────────────┐       │
│  Mobile App  │───────┘ (calls FastAPI directly)
└──────────────┘
```

**Pros**: Next.js handles web auth/SSR naturally, mobile hits FastAPI directly  
**Cons**: Extra hop for web requests, BFF adds complexity, more Next.js API code to maintain  
**Migration**: Drop BFF when mobile is primary

---

## My Recommendation: **Approach A** (now) → **Approach B** (Phase 2)

1. **Start with Approach A** — single FastAPI container with domain modules. Fix all 15 audit bugs. Deploy to Railway/Render free tier. Next.js becomes pure UI (no API routes).

2. **Evolve to Approach B** when you add GPU-heavy models (TFT training, HypCD inference at scale). Extract the Celery worker into a separate container with GPU access.

3. **Approach C is rejected** — it keeps the BFF anti-pattern that caused your current problems. The mobile app would need to bypass it anyway.

---

## Hybrid API Protocol Stack (Confirmed)

Based on the analysis, here's the confirmed protocol design:

| Communication                | Protocol                 | When                                                   |
| ---------------------------- | ------------------------ | ------------------------------------------------------ |
| Client → Backend (CRUD)      | **REST** (OpenAPI)       | All standard operations                                |
| Backend → Client (streaming) | **SSE**                  | Agent thoughts, training progress, live forecasts      |
| Mobile → Backend (gradients) | **gRPC** (Protobuf)      | Federated learning gradient uploads, model weight sync |
| Internal (API → Worker)      | **Redis Queue** (Celery) | Training jobs, batch classification                    |
| External → Backend           | **Webhooks**             | AA data delivery, Stripe callbacks                     |

---

## What Happens to the Next.js API Routes?

**They all get deleted.** Every line of backend logic currently in `apps/web/app/api/` moves to FastAPI domain modules:

| Current Next.js Route                                              | → New FastAPI Domain  |
| ------------------------------------------------------------------ | --------------------- |
| `POST /api/import` (219 lines of Supabase inserts, fingerprinting) | `ingestion/router.py` |
| `POST /api/decrypt-xlsx`                                           | `ingestion/router.py` |
| `POST /api/ingest`                                                 | `ingestion/router.py` |
| `GET /api/transactions`                                            | `accounts/router.py`  |

The Next.js app becomes a **pure React client** that calls the FastAPI REST API.
