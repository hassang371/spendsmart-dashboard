import asyncio
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
from dotenv import load_dotenv

from apps.worker.job_states import InvalidTransitionError, JobStatus, transition
from supabase import Client, create_client

# Imports

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables from root .env only
load_dotenv()

# Support both standard SUPABASE_URL and Next.js public convention as fallback
URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
# Use Service Role Key for background worker to bypass RLS
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY")

if not URL:
    logger.error("SUPABASE_URL not set (also checked NEXT_PUBLIC_SUPABASE_URL)")

if not KEY:
    logger.warning("SUPABASE_SERVICE_ROLE_KEY not found. Worker might fail to update jobs due to RLS.")


def get_supabase() -> Client:
    return create_client(URL, KEY)


def upsert_scheduled_cashflows(supabase: Client, user_id: str, rules) -> int:
    """Upsert detected ``RecurrenceRule`` rows into ``scheduled_cashflows``.

    Idempotent. Per RFC-005 §Data Model Changes the unique key includes
    ``(user_id, merchant, amount, category_bucket, rrule_freq,
    day_of_month, day_of_week, source)``; re-running with the same rules
    refreshes ``next_occurrence`` / ``confidence`` only.

    Returns the number of rows submitted (best-effort — Supabase upsert
    response payload is the source of truth in production but we don't
    block on it). Failures bubble up to the caller, which logs and
    continues — RFC-005 explicitly classifies upstream upsert errors as
    non-fatal for training.
    """
    if not rules:
        return 0
    payload: list[dict] = []
    for rule in rules:
        payload.append(
            {
                "user_id": user_id,
                "merchant": rule.merchant,
                "amount": float(rule.amount),
                "category_bucket": rule.category_bucket,
                "rrule_freq": rule.rrule_freq,
                "day_of_month": rule.day_of_month,
                "day_of_week": rule.day_of_week,
                "next_occurrence": rule.next_occurrence.isoformat(),
                "end_date": rule.end_date.isoformat() if rule.end_date else None,
                "confidence": float(rule.confidence),
                "source": rule.source,
                "is_active": True,
            }
        )
    supabase.table("scheduled_cashflows").upsert(
        payload,
        on_conflict="user_id,merchant,amount,category_bucket,rrule_freq,day_of_month,day_of_week,source",
    ).execute()
    return len(payload)


def train_model(job_id: str, user_id: str):
    """
    Executes the TFT training pipeline:
      fetch transactions -> prepare features -> train model -> save checkpoint.
    """
    from datetime import date, timedelta

    from packages.forecasting.dataset import prepare_training_data
    from packages.forecasting.scheduler import (
        detect_recurring_cashflows,
        project_scheduled_cashflows,
    )
    from packages.forecasting.trainer import (
        MINIMUM_DAYS,
        fetch_user_transactions,
        run_training,
        save_checkpoint_to_supabase,
    )

    supabase = get_supabase()
    logger.info(f"Starting training for user {user_id} (Job {job_id})")

    def update_logs(msg: str):
        supabase.table("training_jobs").update({"logs": msg}).eq("id", job_id).execute()
        logger.info(f"[{job_id}] {msg}")

    # 1. Fetch data
    update_logs("Fetching transactions from database...")
    df = fetch_user_transactions(supabase, user_id)
    tx_count = len(df)
    update_logs(f"Loaded {tx_count} transactions. Preparing features...")

    # 1a. RFC-005 Layer 1 — detect recurring cashflows + upsert. Failure
    # to upsert is non-fatal so a transient DB blip on this auxiliary
    # table never blocks training.
    rules = []
    try:
        rules = detect_recurring_cashflows(df)
        upsert_scheduled_cashflows(supabase, user_id, rules)
    except Exception as exc:
        logger.warning(f"[{job_id}] scheduled_cashflows upsert failed (non-fatal): {exc}")

    # 1b. Project scheduled events across the training horizon so the
    # panel can attach them as known-future covariates. We project from
    # the first transaction date through ``today + MAX_PREDICTION_LENGTH``
    # so future inference draws from the same projection surface.
    scheduled_df = None
    try:
        if rules:
            today = date.today()
            horizon_start = pd.to_datetime(df["date"]).min().date()
            horizon_end = today + timedelta(days=30)
            scheduled_df = project_scheduled_cashflows(rules, horizon_start, horizon_end)
    except Exception as exc:
        logger.warning(f"[{job_id}] scheduled cashflow projection failed (non-fatal): {exc}")
        scheduled_df = None

    # 2. Prepare features (panel)
    enriched = prepare_training_data(
        df,
        min_days=MINIMUM_DAYS,
        user_id=user_id,
        scheduled_df=scheduled_df,
    )
    update_logs(
        f"Prepared {len(enriched)} panel rows "
        f"({enriched['date'].nunique()} days × {enriched['category_bucket'].nunique()} buckets). "
        f"Starting TFT training..."
    )

    # 3. Train
    trainer, model, dataset = run_training(enriched, max_epochs=30)

    # 4. Metrics
    best_val_loss = float(trainer.callback_metrics.get("val_loss", 0))
    metrics = {
        "val_loss": round(best_val_loss, 6),
        "epochs_trained": trainer.current_epoch + 1,
        "days_of_data": len(enriched),
        "transaction_count": tx_count,
    }

    # 5. Save checkpoint
    update_logs("Saving model checkpoint...")
    checkpoint_path = save_checkpoint_to_supabase(supabase, trainer, user_id, job_id)

    # 6. Attach results to job
    supabase.table("training_jobs").update(
        {
            "checkpoint_path": checkpoint_path,
            "metrics": metrics,
            "transaction_count": tx_count,
        }
    ).eq("id", job_id).execute()

    summary = f"Training complete. Val loss: {best_val_loss:.6f}. Checkpoint: {checkpoint_path}"
    logger.info(f"[{job_id}] {summary}")
    return summary


def process_next_job(supabase: Client) -> bool:
    """Polls for a single pending job and processes it. Returns True if a job was found, False otherwise."""
    try:
        # Training jobs for the forecasting worker only.
        # Adapter-training jobs are queued via Celery and carry
        # source_row_count/celery_task_id metadata.
        response = supabase.table("training_jobs").select("*").eq("status", JobStatus.PENDING.value).limit(20).execute()

        if response.data:
            candidates = [
                job
                for job in response.data
                if (job.get("job_type") == "forecasting" or str(job.get("logs") or "").startswith("forecasting:"))
                and not job.get("celery_task_id")
            ]
            if not candidates:
                return False

            job = candidates[0]
            job_id = job["id"]
            user_id = job["user_id"]

            logger.info(f"Claiming training job {job_id}")
            now_iso = datetime.now(timezone.utc).isoformat()

            if job["status"] == JobStatus.COMPLETED.value:
                logger.info(f"Job {job_id} already completed. Skipping.")
                return True

            try:
                transition(job["status"], JobStatus.PROCESSING.value)
            except InvalidTransitionError as e:
                logger.warning(f"Job {job_id} bad transition: {e}")
                return True

            # Mark processing
            claim_response = (
                supabase.table("training_jobs")
                .update({"status": JobStatus.PROCESSING.value, "updated_at": now_iso})
                .eq("id", job_id)
                .eq("status", JobStatus.PENDING.value)
                .execute()
            )

            if not claim_response.data:
                logger.info(f"Job {job_id} was already claimed by another worker.")
                return True

            try:
                logs = train_model(job_id, user_id)

                completed_at = datetime.now(timezone.utc).isoformat()
                supabase.table("training_jobs").update(
                    {
                        "status": JobStatus.COMPLETED.value,
                        "logs": logs,
                        "updated_at": completed_at,
                    }
                ).eq("id", job_id).execute()

                logger.info(f"Job {job_id} completed successfully.")

                # RFC-004 — publish a cache-invalidation message AFTER
                # the DB commit so any subscriber that reacts will see
                # the new checkpoint when it reloads. Failure is
                # non-fatal: counted + logged, never raised.
                try:
                    import redis as _redis

                    from packages.forecasting.cache_invalidation import (
                        publish_invalidation_sync,
                    )

                    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
                    redis_client = _redis.from_url(redis_url, socket_connect_timeout=2)
                    publish_invalidation_sync(redis_client, user_id, completed_at)
                except Exception as exc:
                    logger.warning(f"Job {job_id}: cache invalidation publish failed: {exc}")

            except Exception as e:
                logger.error(f"Job {job_id} failed: {e}")
                # BUG-018 fix: Wrap failure status write in nested try/except.
                try:
                    transition(JobStatus.PROCESSING.value, JobStatus.FAILED.value)
                    supabase.table("training_jobs").update(
                        {
                            "status": JobStatus.FAILED,
                            "logs": str(e),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).eq("id", job_id).execute()
                except Exception as status_err:
                    logger.error(
                        f"Job {job_id}: failed to write failure status: {status_err}. "
                        f"Job may remain stuck in 'processing' — manual intervention needed."
                    )
                    for attempt in range(1, 4):
                        try:
                            time.sleep(0.5 * attempt)
                            supabase.table("training_jobs").update(
                                {
                                    "status": JobStatus.FAILED,
                                    "logs": str(e),
                                    "updated_at": datetime.now(timezone.utc).isoformat(),
                                }
                            ).eq("id", job_id).execute()
                            logger.info(f"Job {job_id}: failure status write recovered on retry {attempt}.")
                            break
                        except Exception as retry_err:
                            logger.error(f"Job {job_id}: failure status retry {attempt} failed: {retry_err}")

            return True

        return False

    except Exception as e:
        logger.error(f"Worker loop error: {e}")
        return False


def main():
    if not URL or not KEY:
        logger.error("Missing configuration. Exiting.")
        return

    supabase = get_supabase()
    logger.info("Worker started. Polling for jobs...")

    last_auto_sync: datetime | None = None
    AUTO_SYNC_INTERVAL = timedelta(hours=1)  # Check eligibility every hour; sync_task skips if < 24h stale

    while True:
        had_job = process_next_job(supabase)

        # Run auto-sync on a background schedule
        now = datetime.now(timezone.utc)
        if last_auto_sync is None or (now - last_auto_sync) >= AUTO_SYNC_INTERVAL:
            try:
                from apps.worker.sync_task import run_auto_sync

                result = asyncio.run(run_auto_sync(supabase))
                logger.info("auto_sync synced=%d errors=%d", result["synced"], result["errors"])
            except Exception as exc:
                logger.error("auto_sync_loop_error: %s", exc)
            last_auto_sync = now

        if not had_job:
            time.sleep(5)


if __name__ == "__main__":
    main()
