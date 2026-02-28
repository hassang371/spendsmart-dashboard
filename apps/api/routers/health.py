"""Health check router — liveness + readiness.

IMP-05 fix: Replaced blocking `celery_app.control.inspect().stats()`
with async Redis ping + 2s timeout. The old implementation would hang
for 30s+ if no Celery workers were available, causing cascading
health check failures.
"""

import asyncio
import structlog
from fastapi import APIRouter
from apps.api.core.config import settings

router = APIRouter(tags=["health"])
logger = structlog.get_logger()

REDIS_TIMEOUT_SECONDS = 2


@router.get("/health")
async def health_liveness():
    """Liveness probe — returns 200 if the API process is running.

    This is the fast probe. Kubernetes/load balancers should use this.
    """
    return {"status": "healthy", "service": "api"}


@router.get("/health/ready")
async def health_readiness():
    """Readiness probe — checks Redis connectivity.

    IMP-05 fix: Uses Redis ping with 2s timeout instead of blocking
    celery_app.control.inspect().stats() which could hang for 30s+.
    """
    status = {
        "status": "healthy",
        "services": {
            "api": "up",
            "redis": "unknown",
        },
    }

    # Non-blocking Redis check with timeout
    try:
        import redis

        redis_url = settings.REDIS_URL if settings else "redis://localhost:6379/0"
        r = redis.from_url(redis_url, socket_connect_timeout=REDIS_TIMEOUT_SECONDS)

        # Run ping with timeout
        loop = asyncio.get_event_loop()
        pong = await asyncio.wait_for(
            loop.run_in_executor(None, r.ping),
            timeout=REDIS_TIMEOUT_SECONDS,
        )

        if pong:
            status["services"]["redis"] = "up"
        else:
            status["services"]["redis"] = "down"
            status["status"] = "degraded"
    except asyncio.TimeoutError:
        status["services"]["redis"] = "timeout"
        status["status"] = "degraded"
        logger.warning("redis_health_timeout", timeout_s=REDIS_TIMEOUT_SECONDS)
    except Exception as e:
        status["services"]["redis"] = "down"
        status["status"] = "degraded"
        logger.warning("redis_health_failed", error=str(e))

    return status
