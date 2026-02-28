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
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from apps.api.core.config import settings
from apps.api.core.errors import register_error_handlers
from apps.api.core.logging import setup_logging
from apps.api.core.security_headers import SecurityHeadersMiddleware
from apps.api.core.middleware import RequestIDMiddleware, RequestLoggingMiddleware

# Domain routers (new)
from apps.api.domains.ingestion.router import router as ingestion_router
from apps.api.domains.categorization.router import router as categorization_router
from apps.api.domains.forecasting.router import router as forecasting_router
from apps.api.domains.training.router import router as training_router
from apps.api.domains.anomaly.router import router as anomaly_router
from apps.api.domains.accounts.router import router as accounts_router

# Legacy routers (preserving for backward compat during migration)
from apps.api.routers import health

logger = structlog.get_logger()


MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


class ContentSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject requests with Content-Length exceeding the configured limit.

    Prevents DoS via oversized payloads. CSV uploads are capped at 10 MB
    which is sufficient for thousands of transaction rows.
    """

    def __init__(self, app, max_bytes: int = MAX_REQUEST_BODY_BYTES):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            return JSONResponse(
                status_code=413,
                content={
                    "type": "about:blank",
                    "title": "Content Too Large",
                    "status": 413,
                    "detail": (
                        f"Request body exceeds maximum allowed size of "
                        f"{self._max_bytes // (1024 * 1024)} MB."
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
    setup_logging(
        log_level=settings.log_level,
        json_output=(os.getenv("ENVIRONMENT", "development") == "production"),
    )
    _init_sentry()
    logger.info("app_starting", version="0.5.0")
    yield
    logger.info("app_stopping")


# OpenAPI tag metadata for interactive docs
TAGS_METADATA = [
    {
        "name": "ingestion",
        "description": "CSV/Excel file upload, parsing, and fingerprinting.",
    },
    {
        "name": "categorization",
        "description": "Transaction classification using HypCD model.",
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

# Register RFC 7807 error handlers (ARCH-02 fix)
register_error_handlers(app)

# Middleware is applied in reverse registration order (last added = outermost).
# Order: RequestLogging → RequestID → SecurityHeaders → ContentSizeLimit → CORS → app

# M5: Structured request logging (outermost — wraps entire request lifecycle)
app.add_middleware(RequestLoggingMiddleware)

# M5: Request ID generation/propagation
app.add_middleware(RequestIDMiddleware)

# M3: Security headers (X-Frame-Options, X-Content-Type-Options, CSP, etc.)
is_production = settings.ENVIRONMENT == "production"
app.add_middleware(SecurityHeadersMiddleware, production=is_production)

# M3: Reject bodies > 10 MB before they hit domain logic
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

@app.get("/health", tags=["health"])
async def root_health_check():
    """Liveness probe."""
    return {"status": "ok"}

@app.get("/ready", tags=["health"])
async def root_ready_check():
    """Readiness probe."""
    return {"status": "ready"}

# --- Legacy routers (kept during migration) ---
app.include_router(health.router, prefix="/api/v1")
