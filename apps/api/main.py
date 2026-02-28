"""SCALE API Gateway — FastAPI entry point.

Milestone 1 refactor: Routes now served from domain modules under
apps/api/domains/. Old routers kept temporarily for backward compat.

Fixes:
- ARCH-03: CORS origins from config (was hardcoded to localhost:3000).
- ARCH-02: RFC 7807 error handler registered globally.
"""

import os
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.core.config import settings
from apps.api.core.errors import register_error_handlers
from apps.api.core.logging import setup_logging

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup/shutdown hooks."""
    setup_logging(
        log_level=settings.log_level,
        json_output=(os.getenv("ENVIRONMENT", "development") == "production"),
    )
    logger.info("app_starting", version="0.3.0")
    yield
    logger.info("app_stopping")


app = FastAPI(
    title="SCALE API Gateway",
    description="Bridges the Python intelligence layer to the Next.js frontend.",
    version="0.3.0",
    lifespan=lifespan,
)

# Register RFC 7807 error handlers (ARCH-02 fix)
register_error_handlers(app)

# CORS — ARCH-03 fix: configurable origins from environment
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Domain routers (new modular architecture) ---
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(categorization_router, prefix="/api/v1")
app.include_router(forecasting_router, prefix="/api/v1")
app.include_router(training_router, prefix="/api/v1")
app.include_router(anomaly_router, prefix="/api/v1")
app.include_router(accounts_router, prefix="/api/v1")

# --- Legacy routers (kept during migration) ---
app.include_router(health.router, prefix="/api/v1")
