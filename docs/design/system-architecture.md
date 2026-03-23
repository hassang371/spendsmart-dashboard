# System Architecture — HLD

> **Doc ID:** system-architecture
> **Last Updated:** 2026-03-06
> **Status:** Current
> **Version:** 1.0
> **DRI:** Hassan

## Overview

SCALE (SpendSmart) is an AI-powered personal finance platform built as a **modular monolith** — domain-separated FastAPI backend, pure Next.js frontend, Supabase database, and Celery workers for async compute.

## Architecture Diagram

```mermaid
graph TB
    subgraph Clients["👤 Clients"]
        Web["🌐 Next.js Web App<br/>(Vercel Edge)"]
        Mobile["📱 Mobile App<br/>(Future)"]
    end

    subgraph Gateway["⚙️ FastAPI Gateway"]
        Core["🛡️ Core Layer<br/>Auth | CORS | Rate Limit | Logging"]

        subgraph Domains["📦 Domain Modules"]
            Ing["📥 Ingestion<br/>import, parse, dedup"]
            Cat["🏷️ Categorization<br/>classify, feedback, adapter"]
            Fore["📈 Forecasting<br/>predict, TFT train"]
            Train["🔧 Training<br/>model jobs, status"]
            Anom["🚨 Anomaly<br/>TDA detection"]
            Acc["👤 Accounts<br/>profile, transactions, reclassify"]
            Agg["🏦 Aggregator<br/>AA consent, sync, webhooks"]
        end
    end

    subgraph Infra["🗄️ Infrastructure"]
        DB["💾 Supabase<br/>(Postgres + RLS)"]
        Redis["⚡ Upstash Redis<br/>(Cache + Queue)"]
        Worker["⚙️ Celery Worker<br/>(scale-worker on Railway)"]
        GHCR["📦 GHCR<br/>(Container Registry)"]
        Railway["🚂 Railway<br/>(scale-api + scale-worker)"]
    end

    Web -->|REST| Core
    Mobile -->|REST + gRPC| Core
    Core --> Domains
    Domains --> DB
    Domains --> Redis
    Domains -->|Queue| Worker
    Worker --> DB
    Worker --> Redis
    GHCR -->|deploy by SHA| Railway
```

## Domain Module Structure

```
apps/api/
├── domains/
│   ├── ingestion/       ← Smart Import, file parsing, fingerprinting
│   ├── categorization/  ← MiniLM + cosine-sim classifier, feedback, LinearAdapter
│   ├── forecasting/     ← TFT model, predictions
│   ├── training/        ← Model training jobs, FL aggregation
│   ├── anomaly/         ← TDA anomaly detection (future)
│   ├── accounts/        ← Transactions (paginated), profile, reclassification
│   └── aggregator/      ← Bank account linking (Setu AA), consent, sync, webhooks
├── core/                ← Auth, logging, errors, middleware
├── main.py              ← FastAPI app, registers all domain routers
└── worker.py            ← Celery worker, imports domain tasks
```

Each domain is self-contained with its own router, service layer, schemas, and tests. Domains can be extracted into microservices by replacing direct function calls with REST/gRPC.

## Communication Protocols

| Communication | Protocol | When |
|---|---|---|
| Client → Backend (CRUD) | REST (OpenAPI) | All standard operations |
| Backend → Client (streaming) | SSE | Training progress, live forecasts |
| Mobile → Backend (gradients) | gRPC (Protobuf) | Federated learning gradient uploads |
| Internal (API → Worker) | Redis Queue (Celery) | Training jobs, batch classification |
| External → Backend | Webhooks | AA data delivery, Stripe callbacks |

## Deployment Strategy

```mermaid
graph LR
    subgraph Phase1["Phase 1: $0/month"]
        V1["Vercel<br/>Frontend"]
        R1["Railway<br/>Backend"]
        S1["Supabase Free<br/>Database"]
        U1["Upstash Free<br/>Redis"]
    end

    subgraph Phase2["Phase 2: $50-100/month"]
        V2["Vercel<br/>Frontend"]
        CR["Cloud Run<br/>Auto-scale"]
        SP["Supabase Pro<br/>8GB"]
        UP["Upstash Pro<br/>Redis"]
    end

    subgraph Phase3["Phase 3: Revenue"]
        V3["Vercel<br/>Frontend"]
        K8["GKE/EKS<br/>GPU Nodes"]
        CI["Citus<br/>Sharded DB"]
        RS["Ray Serve<br/>ML Inference"]
    end

    Phase1 -->|Users + Revenue| Phase2
    Phase2 -->|Scale Pressure| Phase3
```

## Non-Functional Requirements

| Category | Phase 1 | Phase 2 | Phase 3 |
|---|---|---|---|
| API latency (p95) | < 500ms | < 200ms | < 100ms |
| Concurrent users | 100 | 1,000 | 10,000+ |
| Data volume | < 1GB | < 50GB | < 1TB |
| Uptime target | 99% | 99.9% | 99.99% |
| Monthly cost | $0 | $50-100 | $500+ |

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Architecture style | Modular monolith | Solo dev, zero budget, ACID needs |
| Frontend framework | Next.js (pure UI) | No API routes, calls FastAPI directly |
| Backend framework | FastAPI | Async, OpenAPI auto-docs, Python ML ecosystem |
| Database | Supabase (Postgres) | Free tier, built-in auth, RLS, realtime |
| Cache/Queue | Upstash Redis | Free tier, serverless, Celery broker |
| Auth | Supabase JWT | Stateless, no server sessions |
| ML inference | In-process (Phase 1) | Single container simplicity |

## Data Flow — Transaction Ingestion to Forecast

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant W as 🌐 Next.js
    participant A as ⚙️ FastAPI
    participant Q as 📬 Redis/Celery
    participant P as 🔍 Ingestion Engine
    participant C as 🤖 Categorizer
    participant F as 📈 Forecasting
    participant D as 💾 Supabase

    U->>W: Upload bank CSV
    W->>A: POST /api/v1/ingestion/upload
    A->>D: Store raw file reference
    A->>Q: enqueue parse_transactions task
    Q->>P: parse_transactions(file_id)
    P->>D: INSERT transactions (deduped)
    P->>Q: enqueue categorize_batch task
    Q->>C: categorize_batch(transaction_ids)
    C->>D: UPDATE transactions.category
    C->>Q: enqueue retrain_forecast task
    Q->>F: retrain_forecast(user_id)
    F->>D: UPDATE forecast_snapshots
    D-->>W: Realtime subscription update
    W-->>U: Dashboard refreshes
```

## CI/CD Artifact Pipeline (LLD 007)

Every push to `main` that passes CI triggers the following artifact and deploy sequence:

| Step | What happens |
|---|---|
| CI passes | `build-push-images` job builds `scale-api:<sha>` and pushes to GHCR |
| SBOM | Syft scans the pushed image and generates an SPDX JSON bill of materials — attached as a workflow artifact (30-day retention) |
| cosign | Image is signed keylessly via Sigstore OIDC — no private key stored; signature recorded in Sigstore's Rekor transparency log; verifiable with `cosign verify ghcr.io/<owner>/scale-api:<sha>` |
| DB migrations | `supabase db push` applies any pending migrations before the container is swapped |
| Staging deploy | `railway up --service scale-api --image <sha>` — same for scale-worker |
| Smoke test | `GET /health` retried 18×10s (180s); CI fails if not 200 |
| Manual approval | GitHub Environment `production` protection rule gates the production deploy |
| Production deploy | Same image SHA deployed to production Railway services |
| Rollback | Trigger `workflow_dispatch` on deploy.yml with a previous SHA to re-deploy |

## Changelog

| Date | Feature | Change |
|---|---|---|
| 2026-03-06 | Initial HLD | Created from archived architecture docs |
| 2026-03-08 | Doc standards | Added Doc ID, Version, DRI metadata; added data flow diagram |
| 2026-03-15 | Account Aggregator | Added Aggregator domain (Setu AA consent + sync); updated Accounts domain description; see docs/features/004-account-aggregator.md |
| 2026-03-16 | v2 Classifier | Updated Categorization domain to reflect MiniLM + LinearAdapter (not HypCD); updated domain module structure |
| 2026-03-22 | BUG-002 fix | AdapterManager removed; single save path is model_registry.save_version(). upsert_model_metadata RPC ensures atomic metadata write. |
| 2026-03-23 | CI/CD Hardening (LLD 006) | Added GHCR container registry to Infrastructure subgraph. CI pushes scale-api:<sha> to GHCR on every main branch push. Refs: docs/features/006-ci-cd-pipeline-hardening.md |
| 2026-03-23 | CD Implementation (LLD 007) | Added Railway (scale-api + scale-worker) to Infrastructure subgraph. Added CI/CD Artifact Pipeline section covering SBOM (Syft), cosign signing, migration step, Railway staging + production deploy, smoke tests, and rollback. Refs: docs/features/007-cd-implementation.md |
