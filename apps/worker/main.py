import os
import time
import logging
from datetime import datetime, timezone
from supabase import create_client, Client
from dotenv import load_dotenv

# Imports

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
load_dotenv(
    "apps/web/.env.local"
)  # Explicitly try loading from web metadata if root fails

URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
# Use Service Role Key for background worker to bypass RLS
KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not URL:
    logger.error("NEXT_PUBLIC_SUPABASE_URL invalid")

if not KEY:
    logger.warning(
        "SUPABASE_SERVICE_ROLE_KEY not found. Worker might fail to update jobs due to RLS."
    )


def get_supabase() -> Client:
    return create_client(URL, KEY)


def train_model(job_id: str, user_id: str):
    """
    Executes the TFT training pipeline:
      fetch transactions -> prepare features -> train model -> save checkpoint.
    """
    from packages.forecasting.trainer import (
        fetch_user_transactions,
        prepare_training_data,
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

    # 2. Prepare features
    enriched = prepare_training_data(df)
    update_logs(f"Prepared {len(enriched)} daily datapoints. Starting TFT training...")

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
    summary = f"Training complete. Val loss: {best_val_loss:.6f}. Checkpoint: {checkpoint_path}"
    logger.info(f"[{job_id}] {summary}")
    return summary


def main():
    if not URL or not KEY:
        logger.error("Missing configuration. Exiting.")
        return

    supabase = get_supabase()
    logger.info("Worker started. Polling for jobs...")

    while True:
        try:
            # Training Jobs (Forecasting / Active Learning)
            response = (
                supabase.table("training_jobs")
                .select("*")
                .eq("status", "pending")
                .limit(1)
                .execute()
            )

            if response.data:
                job = response.data[0]
                job_id = job["id"]
                user_id = job["user_id"]

                logger.info(f"Claiming training job {job_id}")
                now_iso = datetime.now(timezone.utc).isoformat()

                # Mark processing
                claim_response = (
                    supabase.table("training_jobs")
                    .update({"status": "processing", "updated_at": now_iso})
                    .eq("id", job_id)
                    .eq("status", "pending")
                    .execute()
                )

                if not claim_response.data:
                    logger.info(f"Job {job_id} was already claimed by another worker.")
                    continue

                try:
                    logs = train_model(job_id, user_id)

                    supabase.table("training_jobs").update(
                        {
                            "status": "completed",
                            "logs": logs,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).eq("id", job_id).execute()

                    logger.info(f"Job {job_id} completed successfully.")

                except Exception as e:
                    logger.error(f"Job {job_id} failed: {e}")
                    supabase.table("training_jobs").update(
                        {
                            "status": "failed",
                            "logs": str(e),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        }
                    ).eq("id", job_id).execute()

                continue

            # 3. No jobs
            time.sleep(5)

        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
