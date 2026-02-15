"""Celery tasks for async model training."""

import logging
from typing import List, Dict, Optional
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError

from packages.categorization.training_pipeline import (
    HypCDTrainingPipeline,
    TrainingConfig,
)
from packages.categorization.backends.cloud import CloudBackend

logger = logging.getLogger(__name__)


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
    """
    Async task to train HpyCD model.
    
    Args:
        texts: List of transaction descriptions
        labels: List of category labels
        user_id: User ID for job tracking
        job_id: Training job ID in database
        epochs: Number of training epochs
        batch_size: Batch size for training
        learning_rate: Learning rate
        checkpoint_dir: Directory to save checkpoints
        
    Returns:
        Dictionary with training results and metrics
    """
    try:
        logger.info(f"Starting training job {job_id} for user {user_id}")
        
        # Create training config
        config = TrainingConfig(
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            checkpoint_dir=f"{checkpoint_dir}/{user_id}",
            checkpoint_frequency=5,
            num_classes=len(set(labels)),
        )
        
        # Initialize pipeline
        pipeline = HypCDTrainingPipeline(config)
        
        # Data loader function
        def data_loader():
            return texts, labels
        
        # Run training
        metrics = pipeline.train(data_loader)
        
        # Export final model
        model_path = f"{checkpoint_dir}/{user_id}/final_model.pt"
        pipeline.export_model(model_path)
        
        logger.info(f"Training job {job_id} completed successfully")
        
        return {
            "status": "completed",
            "job_id": job_id,
            "user_id": user_id,
            "metrics": metrics,
            "model_path": model_path,
        }
        
    except Exception as exc:
        logger.error(f"Training job {job_id} failed: {exc}")
        
        # Retry on failure
        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
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
