"""Celery tasks for automated toil reduction.

Automates recurring operational work:
- Marking stale training jobs as failed (stuck > 1 hour)
- Cleaning up old checkpoint files (> 30 days)
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict

import structlog
from celery import shared_task

logger = structlog.get_logger()

STALE_JOB_THRESHOLD_HOURS = 1
CHECKPOINT_MAX_AGE_DAYS = 30
DEFAULT_CHECKPOINT_DIR = "/app/checkpoints"


@shared_task
def cleanup_stale_training_jobs() -> Dict:
    """Mark training jobs stuck in 'processing' for over 1 hour as 'failed'.

    Prevents orphaned jobs from confusing users. Runs on Celery Beat schedule
    (recommended: every hour).

    Returns:
        Dict with count of cleaned up jobs.
    """
    try:
        from apps.api.core.auth import get_service_client

        client = get_service_client()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=STALE_JOB_THRESHOLD_HOURS)).isoformat()

        result = (
            client.table("training_jobs")
            .update(
                {
                    "status": "failed",
                    "logs": f"Automatically failed: stuck in processing for over {STALE_JOB_THRESHOLD_HOURS} hour(s).",
                }
            )
            .eq("status", "processing")
            .lt("created_at", cutoff)
            .execute()
        )

        count = len(result.data) if result.data else 0
        if count > 0:
            logger.warning("cleanup_stale_jobs", count=count)
        else:
            logger.info("cleanup_stale_jobs_none_found")

        return {"cleaned_up": count}

    except Exception as e:
        logger.error(f"cleanup_stale_jobs_failed: {e}")
        return {"cleaned_up": 0, "error": str(e)}


@shared_task
def cleanup_old_checkpoints(
    checkpoint_dir: str = DEFAULT_CHECKPOINT_DIR,
    max_age_days: int = CHECKPOINT_MAX_AGE_DAYS,
) -> Dict:
    """Delete checkpoint files older than max_age_days.

    Prevents disk usage from growing unbounded. Keeps the latest checkpoint
    per user directory. Runs on Celery Beat schedule (recommended: daily).

    Returns:
        Dict with count and total size of deleted files.
    """
    deleted_count = 0
    deleted_bytes = 0
    cutoff_time = time.time() - (max_age_days * 86400)

    if not os.path.isdir(checkpoint_dir):
        logger.info("cleanup_checkpoints_dir_missing", dir=checkpoint_dir)
        return {"deleted_count": 0, "deleted_bytes": 0}

    for root, _dirs, files in os.walk(checkpoint_dir):
        # Sort files by modification time, newest first
        checkpoint_files = []
        for f in files:
            if f.endswith((".pt", ".pth")):
                filepath = os.path.join(root, f)
                checkpoint_files.append((filepath, os.path.getmtime(filepath)))

        # Keep the newest checkpoint in each directory, delete old ones
        checkpoint_files.sort(key=lambda x: x[1], reverse=True)
        for i, (filepath, mtime) in enumerate(checkpoint_files):
            # Always keep the newest file in each directory
            if i == 0:
                continue
            if mtime < cutoff_time:
                try:
                    size = os.path.getsize(filepath)
                    os.remove(filepath)
                    deleted_count += 1
                    deleted_bytes += size
                    logger.info(
                        "checkpoint_deleted",
                        path=filepath,
                        age_days=int((time.time() - mtime) / 86400),
                    )
                except OSError as e:
                    logger.warning("checkpoint_delete_failed", path=filepath, error=str(e))

    if deleted_count > 0:
        logger.warning(
            "cleanup_checkpoints_complete",
            deleted_count=deleted_count,
            deleted_mb=round(deleted_bytes / (1024 * 1024), 2),
        )
    else:
        logger.info("cleanup_checkpoints_none_found")

    return {"deleted_count": deleted_count, "deleted_bytes": deleted_bytes}
