"""Health check router with dependency checks."""

from fastapi import APIRouter
from apps.api.celery_app import celery_app

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Comprehensive health check including dependencies.
    
    Returns status of API, Redis, and Celery workers.
    """
    status = {
        "status": "healthy",
        "services": {
            "api": "up",
            "redis": "unknown",
            "celery": "unknown",
        },
    }
    
    # Check Redis
    try:
        celery_app.backend.client.ping()
        status["services"]["redis"] = "up"
    except Exception:
        status["services"]["redis"] = "down"
        status["status"] = "degraded"
    
    # Check Celery workers
    try:
        stats = celery_app.control.inspect().stats()
        if stats:
            status["services"]["celery"] = "up"
            status["services"]["workers"] = list(stats.keys())
        else:
            status["services"]["celery"] = "no_workers"
    except Exception:
        status["services"]["celery"] = "down"
    
    return status
