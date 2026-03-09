"""Celery tasks for async model training (v2).

v2: Uses TransactionClassifier with Linear Adapter.
Training tasks now train the lightweight Linear Adapter from user corrections,
not the full HypCD pipeline.
"""

import logging
import os
from typing import List, Dict, Optional
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from packages.categorization.backends.cloud import CloudBackend

logger = logging.getLogger(__name__)


def _update_job_status(
    job_id: str,
    status: str,
    metrics: Optional[Dict] = None,
    checkpoint_path: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Update training job status in Supabase using service-role client."""
    try:
        from apps.api.core.auth import get_service_client
        client = get_service_client()

        update_data: Dict = {"status": status}
        if metrics:
            update_data["metrics"] = metrics
        if checkpoint_path:
            update_data["checkpoint_path"] = checkpoint_path
        if error:
            update_data["logs"] = error

        client.table("training_jobs").update(update_data).eq("id", job_id).execute()
        logger.info(f"Updated job {job_id} status to {status}")
    except Exception as e:
        logger.error(f"Failed to update job {job_id} status: {e}")


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def train_adapter_task(
    self,
    texts: List[str],
    categories: List[str],
    user_id: str,
    job_id: str,
    epochs: int = 5,
    learning_rate: float = 1e-3,
) -> Dict:
    """Async task to train user's Linear Adapter from corrections.

    v2: Trains only the lightweight Linear Adapter (~10KB), not the full model.
    The frozen MiniLM base model is never retrained.
    """
    try:
        logger.info(f"Starting adapter training job {job_id} for user {user_id}")
        _update_job_status(job_id, "running")

        from apps.api.domains.categorization.service import get_classifier
        classifier = get_classifier()

        adapter = classifier.train_adapter(
            texts=texts,
            categories=categories,
            epochs=epochs,
            lr=learning_rate,
        )

        # Save adapter checkpoint to Supabase Storage
        from packages.categorization.model_registry import save_version
        from apps.api.core.auth import get_service_client
        client = get_service_client()
        
        version_record = save_version(
            client=client,
            user_id=user_id,
            adapter_state_dict=adapter.state_dict(),
            metrics={"epochs": epochs, "learning_rate": learning_rate, "samples": len(texts)},
        )

        logger.info(f"Adapter training job {job_id} completed successfully")
        _update_job_status(
            job_id,
            status="completed",
            checkpoint_path=version_record.storage_path,
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "user_id": user_id,
            "model_path": model_path,
        }

    except Exception as exc:
        logger.error(f"Adapter training job {job_id} failed: {exc}")

        retry_count = self.request.retries
        max_retries = self.max_retries

        if retry_count < max_retries:
            _update_job_status(
                job_id,
                status="running",
                error=f"Attempt {retry_count + 1}/{max_retries + 1} failed: {exc}. Retrying...",
            )

        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
            _update_job_status(
                job_id,
                status="failed",
                error=str(exc),
            )
            return {
                "status": "failed",
                "job_id": job_id,
                "user_id": user_id,
                "error": str(exc),
            }


@shared_task
def classify_transaction_task(
    text: str,
) -> Dict:
    """Classify a single transaction using the v2 classifier.

    Uses the TransactionClassifier singleton (MiniLM + Cosine Similarity).
    """
    try:
        from apps.api.domains.categorization.service import classify_single
        result = classify_single(text)
        return result
    except Exception as exc:
        logger.error(f"Classification failed: {exc}")
        return {
            "category": "Uncategorized",
            "confidence": 0.0,
            "error": str(exc),
        }
