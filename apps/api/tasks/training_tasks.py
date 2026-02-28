"""Celery tasks for async model training.

BUG-01 fix: Task now updates the training_jobs table in Supabase using a
service-role client. Previously, the task returned a result dict but NEVER
wrote the status back to DB, leaving jobs stuck at "queued" forever.
"""

import logging
import os
from typing import List, Dict, Optional
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from packages.categorization.training_pipeline import (
    HypCDTrainingPipeline,
    TrainingConfig,
)
from packages.categorization.backends.cloud import CloudBackend

logger = logging.getLogger(__name__)


def _update_job_status(
    job_id: str,
    status: str,
    metrics: Optional[Dict] = None,
    checkpoint_path: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Update training job status in Supabase using service-role client.

    BUG-01 fix: This uses a service-role key (bypasses RLS) so the Celery
    worker can update the training_jobs table. The old code never did this.
    """
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
def train_model_task(
    self,
    texts: List[str],
    labels: List[int],
    user_id: str,
    job_id: str,
    epochs: int = 50,
    batch_size: int = 32,
    learning_rate: float = 1e-4,
    checkpoint_dir: str = "/app/checkpoints",
) -> Dict:
    """Async task to train HypCD model.

    BUG-01 fix: Now updates training_jobs table with status on
    completion/failure via service-role Supabase client.
    """
    try:
        logger.info(f"Starting training job {job_id} for user {user_id}")
        _update_job_status(job_id, "running")

        config = TrainingConfig(
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            checkpoint_dir=f"{checkpoint_dir}/{user_id}",
            checkpoint_frequency=5,
            num_classes=len(set(labels)),
        )

        pipeline = HypCDTrainingPipeline(config)

        def data_loader():
            return texts, labels

        metrics = pipeline.train(data_loader)

        model_path = f"{checkpoint_dir}/{user_id}/final_model.pt"
        pipeline.export_model(model_path)

        logger.info(f"Training job {job_id} completed successfully")

        # BUG-01 fix: Update DB with completed status
        _update_job_status(
            job_id,
            status="completed",
            metrics=metrics,
            checkpoint_path=model_path,
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "user_id": user_id,
            "metrics": metrics,
            "model_path": model_path,
        }

    except Exception as exc:
        logger.error(f"Training job {job_id} failed: {exc}")

        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
            # BUG-01 fix: Update DB with failed status
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
    model_path: str,
    backend_type: str = "cloud",
) -> Dict:
    """
    Classify a single transaction using a trained model.
    
    Args:
        text: Transaction description
        model_path: Path to trained model
        backend_type: Backend type ('cloud' or 'mobile')
        
    Returns:
        Dictionary with prediction and confidence
    """
    import torch
    from packages.categorization.hypcd import HypCDClassifier
    
    try:
        # Initialize backend
        if backend_type == "cloud":
            from packages.categorization.backends.cloud import CloudBackend
            backend = CloudBackend()
        else:
            from packages.categorization.backends.mobile import MobileBackend
            backend = MobileBackend()
        
        # Load model
        checkpoint = torch.load(model_path, map_location="cpu")
        
        # Initialize classifier
        classifier = HypCDClassifier(
            backend=backend,
            num_classes=checkpoint["config"]["num_classes"],
            proj_dim=checkpoint["config"]["proj_dim"],
            backend_type=backend_type,
        )
        classifier.load_state_dict(checkpoint["classifier"])
        classifier.eval()
        
        # Get embedding and predict
        with torch.no_grad():
            embedding = backend.embed(text).unsqueeze(0)
            hyp_embedding = classifier.embedder.projector(embedding)
            logits = classifier.classifier(hyp_embedding)
            probs = torch.softmax(logits, dim=-1)
            pred_idx = torch.argmax(probs, dim=-1).item()
            confidence = probs[0][pred_idx].item()
        
        # Map to category name
        category = classifier.labels[pred_idx]
        
        return {
            "category": category,
            "confidence": confidence,
            "all_probabilities": {
                label: prob.item()
                for label, prob in zip(classifier.labels, probs[0])
            },
        }
        
    except Exception as exc:
        logger.error(f"Classification failed: {exc}")
        return {
            "category": "Uncategorized",
            "confidence": 0.0,
            "error": str(exc),
        }
