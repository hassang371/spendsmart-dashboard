"""SCALE API Gateway — FastAPI entry point.

Milestone 1 refactor: Routes now served from domain modules under
apps/api/domains/. Old routers kept temporarily for backward compat.

Fixes:
- ARCH-03: CORS origins from config (was hardcoded to localhost:3000).
- ARCH-02: RFC 7807 error handler registered globally.

M3 Security Hardening:
- SecurityHeadersMiddleware: X-Frame-Options, X-Content-Type-Options, HSTS, CSP
- CORS: explicit methods/headers allowlist + 24h preflight cache
- ContentSizeLimitMiddleware: reject oversized request bodies (prevent DoS)

M5 Monitoring & Observability:
- RequestIDMiddleware: UUID per request, X-Request-ID header propagation
- RequestLoggingMiddleware: structured access logs with duration_ms
- Sentry: error tracking + performance monitoring (optional, via SENTRY_DSN)
"""

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.core.config import settings
from apps.api.core.errors import register_error_handlers
from apps.api.core.logging_config import setup_logging, structlog_middleware
from apps.api.core.rate_limiter import RateLimiter, rate_limit_dependency
from apps.api.core.security_headers import SecurityHeadersMiddleware
from apps.api.domains.accounts.router import router as accounts_router
from apps.api.domains.aggregator.router import router as aggregator_router
from apps.api.domains.anomaly.router import router as anomaly_router
from apps.api.domains.categorization.router import router as categorization_router
from apps.api.domains.forecasting.router import router as forecasting_router

# Domain routers (new)
from apps.api.domains.ingestion.router import router as ingestion_router
from apps.api.domains.metrics.router import (
    client_event_router as metrics_client_event_router,
)
from apps.api.domains.metrics.router import (
    prom_router as metrics_prom_router,
)
from apps.api.domains.training.router import router as training_router

# Legacy routers (preserving for backward compat during migration)
from apps.api.routers import health

logger = structlog.get_logger()


MAX_REQUEST_BODY_BYTES = 500 * 1024 * 1024  # 500 MB (large Excel files)


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length exceeding the configured limit.

    Prevents DoS via oversized payloads. Uploads capped at 500 MB
    to support large bank statement files (250k+ rows).
    """

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY_BYTES):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                length_val = int(content_length)
            except ValueError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "type": "about:blank",
                        "title": "Invalid Content-Length",
                        "status": 400,
                        "detail": ("Content-Length header must be a valid integer."),
                    },
                )

            if length_val > self._max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "type": "about:blank",
                        "title": "Content Too Large",
                        "status": 413,
                        "detail": (
                            f"Request body exceeds maximum allowed size of " f"{self._max_bytes // (1024 * 1024)} MB."
                        ),
                    },
                )

        return await call_next(request)


def _init_sentry() -> None:
    """Initialize Sentry error tracking if SENTRY_DSN is configured."""
    dsn = settings.SENTRY_DSN if settings else ""
    if not dsn:
        return
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            environment=settings.ENVIRONMENT,
            release=settings.APP_VERSION,
            send_default_pii=False,
        )
        logger.info("sentry_initialized", environment=settings.ENVIRONMENT)
    except Exception as exc:
        logger.warning("sentry_init_failed", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown hooks."""
    setup_logging(is_dev=(os.getenv("ENVIRONMENT", "development") != "production"))
    _init_sentry()
    logger.info("app_starting", version="0.5.0")

    # Initialize Redis-backed rate limiter for the /ingest/import endpoint
    import redis as _redis

    _redis_client = None
    try:
        _redis_client = _redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
        )
        _redis_client.ping()
        app.state.import_rate_limiter = rate_limit_dependency(
            RateLimiter(_redis_client, max_requests=10, window_seconds=60)
        )
        logger.info("rate_limiter_initialized", endpoint="/ingest/import")
    except Exception as e:
        logger.warning("rate_limiter_unavailable", error=str(e))
        app.state.import_rate_limiter = None
        _redis_client = None

    # RFC-004 — TFT model cache + warm endpoint rate limiter +
    # client-event rate limiter + Redis pub-sub subscriber.
    import functools

    from packages.forecasting.cache import TFTModelCache, default_supabase_loader
    from packages.forecasting.cache_invalidation import start_subscriber

    app.state.tft_cache = TFTModelCache()

    # Stage 5: wire the production Supabase-backed loader. The cache
    # was instantiated without a loader by Stage 3 (so unit tests could
    # plug in mocks); production wiring lives here. We capture the
    # service-role client so the loader can read training_jobs (RLS-
    # bypassed) and download checkpoints from Storage.
    try:
        from supabase import create_client

        _service_supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        app.state.tft_cache.set_loader(functools.partial(default_supabase_loader, _service_supabase))
        logger.info("tft_cache_loader_wired")
    except Exception as exc:
        logger.warning("tft_cache_loader_unavailable", error=str(exc))

    logger.info(
        "tft_cache_initialized",
        max_entries=app.state.tft_cache._max_entries,
        max_bytes=app.state.tft_cache._max_bytes,
        ttl_seconds=app.state.tft_cache._ttl,
    )

    if _redis_client is not None:
        try:
            app.state.warm_rate_limiter = rate_limit_dependency(
                RateLimiter(_redis_client, max_requests=1, window_seconds=300)
            )
            app.state.client_event_rate_limiter = rate_limit_dependency(
                RateLimiter(_redis_client, max_requests=30, window_seconds=60)
            )
        except Exception as e:
            logger.warning("warm_rate_limiter_unavailable", error=str(e))
            app.state.warm_rate_limiter = None
            app.state.client_event_rate_limiter = None
    else:
        app.state.warm_rate_limiter = None
        app.state.client_event_rate_limiter = None

    # Subscribe to cache-invalidation pub-sub. We use redis.asyncio to
    # match the async subscriber loop. Failure to start is non-fatal —
    # the cache still works, just without cross-worker invalidation.
    app.state.tft_cache_subscriber_task = None
    app.state.tft_cache_async_redis = None
    try:
        from redis import asyncio as redis_asyncio

        async_redis = redis_asyncio.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=2,
        )
        # Touch the connection so a misconfigured REDIS_URL fails fast.
        await async_redis.ping()
        app.state.tft_cache_async_redis = async_redis
        app.state.tft_cache_subscriber_task = start_subscriber(async_redis, app.state.tft_cache)
        logger.info("tft_cache_subscriber_started")
    except Exception as e:
        logger.warning("tft_cache_subscriber_unavailable", error=str(e))

    # Eagerly initialize the MiniLM classifier in background thread
    # so the first import doesn't wait for model loading.
    # /ready returns 503 until this completes.
    import asyncio

    app.state.classifier_ready = False

    async def _warmup_classifier():
        try:
            from apps.api.domains.categorization.service import get_classifier

            await asyncio.to_thread(get_classifier)
            logger.info("classifier_warmed_up")
        except Exception as e:
            logger.warning("classifier_warmup_failed", error=str(e))
        finally:
            app.state.classifier_ready = True

    asyncio.create_task(_warmup_classifier())

    yield

    # Shutdown: stop the pub-sub subscriber and close async Redis.
    sub_task = getattr(app.state, "tft_cache_subscriber_task", None)
    if sub_task is not None:
        sub_task.cancel()
        try:
            await sub_task
        except (asyncio.CancelledError, Exception):
            pass
    async_redis = getattr(app.state, "tft_cache_async_redis", None)
    if async_redis is not None:
        try:
            await async_redis.aclose()
        except Exception:
            pass
    logger.info("app_stopping")


# OpenAPI tag metadata for interactive docs
TAGS_METADATA = [
    {
        "name": "ingestion",
        "description": "CSV/Excel file upload, parsing, and fingerprinting.",
    },
    {
        "name": "categorization",
        "description": "Transaction classification using MiniLM + Cosine Similarity.",
    },
    {
        "name": "forecasting",
        "description": "Financial forecasting and predictions.",
    },
    {
        "name": "training",
        "description": "ML model training job management.",
    },
    {
        "name": "anomaly",
        "description": "Anomaly detection and alerts (TDA-based).",
    },
    {
        "name": "accounts",
        "description": "User transactions (paginated + filtered), profile, and settings.",
    },
    {
        "name": "health",
        "description": "Liveness and readiness probes.",
    },
]

app = FastAPI(
    title="SCALE API Gateway",
    description=(
        "AI-powered financial platform API. Provides transaction management, "
        "ML-based categorization, forecasting, and anomaly detection."
    ),
    version="0.5.0",
    lifespan=lifespan,
    openapi_tags=TAGS_METADATA,
    license_info={
        "name": "MIT",
    },
)

# Register RFC 9457 error handlers
register_error_handlers(app)

# Middleware is applied in reverse registration order (last added = outermost).
# Order: Structlog → SecurityHeaders → ContentSizeLimit → CORS → app

# M5: Structured request logging & Request ID generation/propagation
app.add_middleware(BaseHTTPMiddleware, dispatch=structlog_middleware)

# M3: Security headers (X-Frame-Options, X-Content-Type-Options, CSP, etc.)
is_production = settings.ENVIRONMENT == "production"
app.add_middleware(SecurityHeadersMiddleware, production=is_production)

# M3: Reject bodies > 500 MB before they hit domain logic (large bank statement files).
# Note: only checks Content-Length header; chunked uploads are bounded by
# the router-level MAX_UPLOAD_BYTES check instead.
app.add_middleware(ContentSizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)

# ARCH-03 fix + M3 hardening: explicit CORS allowlist, preflight cache
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=86400,
)

# --- Domain routers (new modular architecture) ---
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(categorization_router, prefix="/api/v1")
app.include_router(forecasting_router, prefix="/api/v1")
app.include_router(training_router, prefix="/api/v1")
app.include_router(anomaly_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")
app.include_router(aggregator_router, prefix="/api/v1")
app.include_router(metrics_client_event_router, prefix="/api/v1")

# Prometheus exposition route — root-mounted (no /api/v1 prefix) so
# scrape configs can hit a stable, prefix-free path.
app.include_router(metrics_prom_router)


@app.get("/health", tags=["health"])
async def root_health_check():
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/ready", tags=["health"])
async def root_ready_check(request: Request):
    """Readiness probe — returns 503 until classifier warmup completes."""
    if not getattr(request.app.state, "classifier_ready", False):
        return JSONResponse(
            status_code=503,
            content={"status": "warming_up"},
        )
    return {"status": "ready"}


# --- Legacy routers (kept during migration) ---
app.include_router(health.router, prefix="/api/v1")
