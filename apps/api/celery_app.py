"""Celery application configuration for async training jobs."""

import os
from celery import Celery

# Use Redis as broker and backend
redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "scale_training",
    broker=redis_url,
    backend=redis_url,
    include=["apps.api.tasks.training_tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    worker_prefetch_multiplier=1,  # Process one task at a time per worker
    result_expires=3600 * 24,  # Results expire after 24 hours
)

# Optional: Configure task routing
celery_app.conf.task_routes = {
    "apps.api.tasks.training_tasks.*": {"queue": "training"},
}

if __name__ == "__main__":
    celery_app.start()
