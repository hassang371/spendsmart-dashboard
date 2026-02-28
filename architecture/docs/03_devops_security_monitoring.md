# SCALE App — Deep Dive: DevOps, CI/CD, Security & Monitoring

---

## 1. DevOps

### 1.1 Dockerfile Redesign

**Current problems:**

- Copies `.env.local` into image (security risk — secrets baked into image)
- Runs as root (container escape risk)
- No separate target for worker
- No `.dockerignore` (bloated image)

**New Dockerfile (multi-stage, multi-target):**

```dockerfile
# ============ Stage 1: Builder ============
FROM python:3.11-slim AS builder
WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============ Stage 2: Runtime Base ============
FROM python:3.11-slim AS runtime-base
WORKDIR /app

# Non-root user
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy application code (NO .env files)
COPY apps/ ./apps/
COPY packages/ ./packages/

RUN mkdir -p /app/checkpoints /app/models && \
    chown -R appuser:appuser /app

# ============ Target: API ============
FROM runtime-base AS api
USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

# ============ Target: Worker ============
FROM runtime-base AS worker
USER appuser

CMD ["celery", "-A", "apps.api.celery_app", "worker", "--loglevel=info", "--queues=training", "--concurrency=2"]
```

**Key improvements:**

- **No secrets in image** — `.env` mounted at runtime via docker-compose or platform env vars
- **Non-root user** — `appuser` for both API and worker
- **Separate targets** — `docker build --target api .` vs `--target worker .`
- **No `requests` in healthcheck** — uses stdlib `urllib` (smaller dependency surface)

### 1.2 `.dockerignore`

```
.git
.github
.agents
.gemini
.venv
__pycache__
*.pyc
node_modules
.next
.env*
*.md
architecture/
references/
apps/web/
checkpoints/
*.pt
*.pth
```

> [!IMPORTANT]
> This reduces image size by ~80%. The `apps/web/` directory is excluded because the frontend deploys to Vercel separately.

### 1.3 `docker-compose.yml` Hardened

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    deploy:
      resources:
        limits:
          memory: 128M

  api:
    build:
      context: .
      target: api # NEW: separate target
    ports:
      - "8000:8000"
    env_file: .env # NEW: env file, not inline
    environment:
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=info
      - ENVIRONMENT=development
    volumes:
      - ./apps:/app/apps # Hot reload in dev
      - ./packages:/app/packages
      - ./models:/app/models # Model files
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test:
        [
          "CMD",
          "python",
          "-c",
          "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')",
        ]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    restart: unless-stopped

  worker:
    build:
      context: .
      target: worker # NEW: separate target
    env_file: .env
    environment:
      - REDIS_URL=redis://redis:6379/0
      - LOG_LEVEL=info
      - ENVIRONMENT=development
    volumes:
      - ./models:/app/models
      - ./checkpoints:/app/checkpoints
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      replicas: 1 # Reduced from 2 for dev

  flower:
    image: mher/flower:latest
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
      - FLOWER_PORT=5555
      - FLOWER_BASIC_AUTH=${FLOWER_USER}:${FLOWER_PASSWORD} # NEW: auth
    depends_on:
      - redis
      - worker
    profiles:
      - monitoring # Only start with --profile monitoring

volumes:
  redis_data:
```

### 1.4 Secrets Management Strategy

| Secret                            | Where Stored                                       | Accessed By         |
| --------------------------------- | -------------------------------------------------- | ------------------- |
| `SUPABASE_URL`                    | `.env` (local) / Platform env (prod)               | API, Worker         |
| `SUPABASE_ANON_KEY`               | `.env` / Platform env                              | API (client-facing) |
| `SUPABASE_SERVICE_KEY`            | `.env` / Platform env                              | Worker only         |
| `REDIS_URL`                       | `docker-compose.yml` (local) / Platform env (prod) | API, Worker         |
| `SENTRY_DSN`                      | Platform env                                       | API                 |
| `FLOWER_USER` / `FLOWER_PASSWORD` | `.env`                                             | Flower              |
| `ALLOWED_ORIGINS`                 | Platform env                                       | API                 |

**Rules:**

1. **Never** commit `.env` files (already in `.gitignore`)
2. **Never** bake secrets into Docker images
3. Use platform-level secrets (Railway secrets, GitHub secrets) for prod
4. `.env.example` documents all required vars with dummy values

### 1.5 Database Migrations (Supabase CLI)

```bash
# Install Supabase CLI
brew install supabase/tap/supabase

# Link to remote project
supabase link --project-ref <your-project-ref>

# Create a new migration
supabase migration new add_uploaded_files_table

# Edit the migration file in supabase/migrations/

# Apply locally (requires local Supabase)
supabase db reset

# Push to remote
supabase db push

# Diff remote vs local (detect drift)
supabase db diff --linked
```

**Migration workflow:**

```
Developer makes schema change
  → Creates migration file via `supabase migration new`
  → Tests locally with `supabase db reset`
  → Commits migration file to git
  → CI runs `supabase db push` on deploy
```

---

## 2. CI/CD Pipeline

### 2.1 Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CI Pipeline (on PR)                       │
│                                                             │
│  ┌─────────┐  ┌─────────────┐  ┌──────────┐  ┌─────────┐  │
│  │ Lint    │  │ Security    │  │ Test     │  │ Build   │  │
│  │ (ruff,  │  │ (bandit,    │  │ (pytest, │  │ (Docker │  │
│  │  eslint │→ │  pip-audit, │→ │  vitest) │→ │  image) │  │
│  │  mypy)  │  │  gitleaks)  │  │          │  │         │  │
│  └─────────┘  └─────────────┘  └──────────┘  └─────────┘  │
│       ↓              ↓              ↓             ↓        │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Security Gate (pass/fail)               │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│               CD Pipeline (on merge to main)                │
│                                                             │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Build &  │  │ Deploy to    │  │ Post-deploy           │ │
│  │ Push     │→ │ Staging      │→ │ • Health check        │ │
│  │ Image    │  │ (Railway)    │  │ • Smoke test          │ │
│  └──────────┘  └──────────────┘  │ • DB migrate          │ │
│                                  └───────────────────────┘ │
│                                           ↓ (manual gate)  │
│                                  ┌───────────────────────┐ │
│                                  │ Deploy to Production  │ │
│                                  └───────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 CI Workflow: `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  # ===== Stage 1: Fast Feedback (< 1 min) =====
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install linters
        run: pip install ruff mypy

      - name: Ruff lint
        run: ruff check apps/api/ packages/

      - name: Ruff format check
        run: ruff format --check apps/api/ packages/

      - name: Mypy type check
        run: mypy apps/api/ --ignore-missing-imports

  lint-frontend:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: apps/web/package-lock.json

      - run: cd apps/web && npm ci
      - run: cd apps/web && npx eslint . --max-warnings 0
      - run: cd apps/web && npx tsc --noEmit

  # ===== Stage 2: Security Scanning (< 3 min) =====
  security:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      # Secret scanning
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

      # Python SAST
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install bandit pip-audit
      - name: Bandit (Python SAST)
        run: bandit -r apps/api/ packages/ -ll -ii
      - name: pip-audit (dependency vulnerabilities)
        run: pip-audit -r requirements.txt

  # ===== Stage 3: Tests (< 5 min) =====
  test-backend:
    needs: [lint]
    runs-on: ubuntu-latest
    timeout-minutes: 10
    services:
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: --health-cmd "redis-cli ping" --health-interval 10s
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip

      - name: Install dependencies
        run: pip install -r requirements.txt && pip install pytest pytest-cov pytest-asyncio

      - name: Run tests with coverage
        run: |
          python -m pytest apps/api/tests/ -v \
            --cov=apps/api --cov-report=xml \
            --tb=short --no-header
        env:
          REDIS_URL: redis://localhost:6379/0
          ENVIRONMENT: test

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  test-frontend:
    needs: [lint-frontend]
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
          cache-dependency-path: apps/web/package-lock.json

      - run: cd apps/web && npm ci
      - run: cd apps/web && npx vitest run --coverage

  # ===== Stage 4: Build (< 5 min) =====
  build:
    needs: [test-backend, test-frontend, security]
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build API image
        uses: docker/build-push-action@v5
        with:
          context: .
          target: api
          push: false
          tags: scale-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Trivy container scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: scale-api:${{ github.sha }}
          format: table
          exit-code: 1
          severity: CRITICAL,HIGH
```

### 2.3 CD Workflow: `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  deploy-staging:
    runs-on: ubuntu-latest
    environment:
      name: staging
      url: ${{ steps.deploy.outputs.url }}
    steps:
      - uses: actions/checkout@v4

      # Deploy to Railway (or Render)
      - name: Deploy to Railway
        id: deploy
        uses: bervProject/railway-deploy@main
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN }}
          service: scale-api

      # Post-deploy verification
      - name: Health check
        run: |
          sleep 30
          curl -f ${{ steps.deploy.outputs.url }}/api/v1/health || exit 1

      - name: Smoke test
        run: |
          curl -f ${{ steps.deploy.outputs.url }}/api/v1/health/ready || exit 1

  deploy-production:
    needs: [deploy-staging]
    runs-on: ubuntu-latest
    environment:
      name: production
      url: https://api.scale-app.com
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Production
        uses: bervProject/railway-deploy@main
        with:
          railway_token: ${{ secrets.RAILWAY_TOKEN_PROD }}
          service: scale-api-prod
```

### 2.4 Environment Promotion Strategy

```
Feature branch → PR → CI runs → merge to develop
                                    ↓
                              Auto-deploy to staging
                                    ↓
                              Manual smoke test
                                    ↓
                              PR from develop → main
                                    ↓
                              Auto-deploy to production
                                    ↓
                              Health check gate
```

| Environment | Branch  | Auto-deploy        | DB                         | URL                   |
| ----------- | ------- | ------------------ | -------------------------- | --------------------- |
| Local       | any     | n/a                | Docker Postgres            | localhost:8000        |
| Staging     | develop | ✅                 | Supabase (staging project) | staging.api.scale.app |
| Production  | main    | ✅ (after staging) | Supabase (prod project)    | api.scale.app         |

---

## 3. Security

### 3.1 OWASP Top 10 Mapped to SCALE

| #   | Vulnerability            | SCALE Risk                                                                       | Mitigation                                                            |
| --- | ------------------------ | -------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| A01 | **Injection**            | ⚠️ Medium — Supabase client uses parameterized queries but raw SQL in some paths | Use Supabase client exclusively, Pydantic validation on all inputs    |
| A02 | **Broken Auth**          | ⚠️ Medium — JWT validation not centralized, refresh token bug (BUG-06)           | Centralized auth middleware, fix BUG-06                               |
| A03 | **Sensitive Data**       | 🔴 High — Financial transaction data                                             | TLS everywhere, RLS in Postgres, encrypted at rest (Supabase default) |
| A04 | **XXE**                  | ✅ Low — No XML parsing                                                          | JSON only, Pydantic schemas                                           |
| A05 | **Broken Access**        | ⚠️ Medium — RLS exists but no server-side verification                           | RLS + service-layer ownership checks                                  |
| A06 | **Misconfig**            | 🔴 High — CORS wildcard, no security headers, secrets in Dockerfile              | Fix all (see below)                                                   |
| A07 | **XSS**                  | ✅ Low — React auto-escapes, API returns JSON                                    | CSP headers as defense-in-depth                                       |
| A08 | **Insecure Deser**       | ✅ Low — Pydantic validates all input                                            | Already handled by framework                                          |
| A09 | **Known Vulns**          | ⚠️ Medium — No dependency scanning                                               | pip-audit + npm audit in CI                                           |
| A10 | **Insufficient Logging** | 🔴 High — print() statements, no structured logs                                 | structlog + Sentry (see Monitoring)                                   |

### 3.2 FastAPI Security Middleware Stack

Applied in order (see request lifecycle in system_design.md):

```python
# apps/api/core/security.py

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Equivalent to Express helmet() for FastAPI."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"
        # Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Force HTTPS
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Disable browser features we don't need
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        # CSP (relaxed for API — no HTML served)
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        # Remove server header
        response.headers.pop("server", None)

        return response
```

### 3.3 Rate Limiting (Redis Sliding Window)

```python
# apps/api/core/rate_limiter.py

import time, hashlib
from fastapi import Request, HTTPException
from redis.asyncio import Redis

class RateLimiter:
    """Redis sliding window rate limiter."""

    def __init__(self, redis: Redis, default_limit: int = 100, window_seconds: int = 60):
        self.redis = redis
        self.default_limit = default_limit
        self.window = window_seconds

    async def check(self, request: Request, limit: int | None = None):
        limit = limit or self.default_limit
        # Key: rl:{user_id or IP}:{current_window}
        identifier = getattr(request.state, "user_id", None) or request.client.host
        key = f"rl:{identifier}"
        now = time.time()

        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window)  # Remove old entries
        pipe.zadd(key, {f"{now}": now})                    # Add current request
        pipe.zcard(key)                                     # Count requests in window
        pipe.expire(key, self.window)                       # Auto-cleanup
        results = await pipe.execute()

        request_count = results[2]
        if request_count > limit:
            raise HTTPException(
                status_code=429,
                detail={
                    "type": "rate_limit_exceeded",
                    "title": "Too Many Requests",
                    "detail": f"Rate limit of {limit} requests per {self.window}s exceeded",
                    "retry_after": self.window,
                },
            )

# Rate limit tiers
RATE_LIMITS = {
    "default": {"limit": 100, "window": 60},      # 100/min
    "auth": {"limit": 10, "window": 60},           # 10/min (login, register)
    "import": {"limit": 5, "window": 60},          # 5/min (heavy operation)
    "classify": {"limit": 50, "window": 60},       # 50/min
    "training": {"limit": 3, "window": 3600},      # 3/hour (very heavy)
}
```

### 3.4 CORS Configuration

```python
# In main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    # Phase 1: ["http://localhost:3000"]
    # Prod:    ["https://scale-app.com", "https://www.scale-app.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=86400,  # Cache preflight for 24 hours
)
```

### 3.5 Input Validation (All Inputs via Pydantic)

```python
# Example: apps/api/domains/ingestion/schemas.py
from pydantic import BaseModel, Field, validator
from decimal import Decimal
from datetime import datetime

class TransactionCreate(BaseModel):
    """Validated transaction input — no raw dicts ever reach business logic."""
    transaction_date: datetime
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    description: str = Field(..., min_length=1, max_length=500)
    merchant_name: str | None = Field(None, max_length=200)
    category: str = Field(default="Uncategorized", max_length=100)
    payment_method: str | None = Field(None, max_length=50)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")

    @validator("description")
    def sanitize_description(cls, v):
        """Strip potential injection characters."""
        return v.strip()
```

---

## 4. Monitoring & Observability

### 4.1 The Four Golden Signals

| Signal         | What to Measure      | SCALE Metrics                                      | Alert Threshold          |
| -------------- | -------------------- | -------------------------------------------------- | ------------------------ |
| **Latency**    | Request duration     | `http_request_duration_seconds` (p50, p95, p99)    | p95 > 500ms (Phase 1)    |
| **Traffic**    | Request rate         | `http_requests_total` by endpoint, method          | Informational (no alert) |
| **Errors**     | Error rate           | `http_responses_total{status=5xx}` / total         | > 1% error rate          |
| **Saturation** | Resource utilization | CPU %, memory %, DB connections, Redis connections | > 80% any resource       |

### 4.2 Structured Logging with `structlog`

```python
# apps/api/core/logging.py
import structlog, logging, sys

def setup_logging(log_level: str = "INFO", json_output: bool = True):
    """Configure structured logging for the entire application."""

    processors = [
        structlog.contextvars.merge_contextvars,     # Thread-safe context
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())  # Pretty for dev

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=log_level)

# Usage in any domain:
import structlog
logger = structlog.get_logger()

# Automatically includes request_id, user_id from context:
logger.info("transaction_imported", count=42, duration_ms=150)
# Output: {"event": "transaction_imported", "count": 42, "duration_ms": 150,
#          "request_id": "abc-123", "user_id": "user-456", "timestamp": "...", "level": "info"}
```

### 4.3 Request Logging Middleware

```python
# apps/api/core/middleware/request_logging.py
import time, uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        # Bind request context (available to ALL log calls during this request)
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            user_agent=request.headers.get("user-agent", ""),
        )

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000
        logger = structlog.get_logger()

        log_method = logger.info if response.status_code < 400 else logger.warning
        if response.status_code >= 500:
            log_method = logger.error

        log_method(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        return response
```

### 4.4 Sentry Integration

```python
# In apps/api/main.py
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration(), CeleryIntegration()],
        traces_sample_rate=0.1,          # 10% of transactions for performance
        profiles_sample_rate=0.1,        # 10% for profiling
        environment=settings.ENVIRONMENT, # "development", "staging", "production"
        release=settings.APP_VERSION,
        send_default_pii=False,          # CRITICAL: no PII in error reports
    )
```

**Sentry free tier gives:**

- 5K errors/month
- 10K performance transactions/month
- 1 user
- Sufficient for Phase 1-2

### 4.5 Health Check Endpoints

```python
# apps/api/domains/health/router.py

@router.get("/health")
async def liveness():
    """Liveness probe: is the process alive? Always returns 200 if reachable."""
    return {"status": "ok", "version": settings.APP_VERSION}

@router.get("/health/ready")
async def readiness(redis: Redis = Depends(get_redis), db = Depends(get_supabase)):
    """Readiness probe: can we serve traffic? Checks all dependencies."""
    checks = {}

    # Redis check (non-blocking, < 5ms)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"

    # DB check (non-blocking, < 50ms)
    try:
        result = db.table("transactions").select("id", count="exact").limit(0).execute()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # HypCD model loaded check
    checks["classifier"] = "ok" if app.state.classifier is not None else "not_loaded"

    all_ok = all(v == "ok" for v in checks.values())

    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "degraded", "checks": checks}
    )
```

### 4.6 Alerting Strategy

| Alert                 | Condition                          | Severity    | Notify Via          | Phase |
| --------------------- | ---------------------------------- | ----------- | ------------------- | ----- |
| API down              | Health check fails 3x              | 🔴 Critical | Sentry + Email      | P1    |
| Error rate > 5%       | 5xx / total > 0.05 for 5 min       | 🔴 Critical | Sentry              | P1    |
| Slow responses        | p95 > 2s for 10 min                | 🟡 Warning  | Sentry              | P1    |
| Training job stuck    | Status = "processing" for > 1 hour | 🟡 Warning  | Sentry              | P1    |
| DB connections high   | Active connections > 80% pool      | 🟡 Warning  | Supabase dashboard  | P2    |
| Redis memory high     | Memory > 80% of limit              | 🟡 Warning  | Upstash dashboard   | P2    |
| Import failures spike | > 10 failed imports in 1 hour      | 🟠 Medium   | Sentry              | P2    |
| Security scan failed  | CI security gate fails             | 🟡 Warning  | GitHub notification | P1    |

### 4.7 SLO Targets

| SLI (Service Level Indicator) | SLO (Target) | Measurement                   | Error Budget (30 days)      |
| ----------------------------- | ------------ | ----------------------------- | --------------------------- |
| Availability                  | 99.9%        | Successful requests / total   | 43 minutes downtime         |
| Latency (p95)                 | < 500ms      | 95th percentile response time | 0.1% of requests may exceed |
| Import success rate           | 99%          | Successful imports / total    | 1% may fail                 |
| Classification accuracy       | > 85%        | Correct category / total      | 15% may be wrong            |

---

## Summary: What Gets Built

| Area           | Phase 1 Deliverables                                                                               | Estimated Effort |
| -------------- | -------------------------------------------------------------------------------------------------- | ---------------- |
| **DevOps**     | Dockerfile (multi-target), `.dockerignore`, hardened `docker-compose.yml`, Supabase migrations     | 1 session        |
| **CI/CD**      | `ci.yml` (lint → security → test → build), `deploy.yml` (staging → prod), DevSecOps scanning       | 1 session        |
| **Security**   | Security headers middleware, Redis rate limiter, CORS hardening, Pydantic validation on all inputs | 1 session        |
| **Monitoring** | structlog setup, request logging middleware, Sentry integration, health/ready endpoints            | 1 session        |
