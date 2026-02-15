"""Router for model inference/classification endpoints."""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from supabase import Client

from apps.api.deps import get_user_client
from apps.api.tasks.training_tasks import classify_transaction_task

router = APIRouter(tags=["classification"])
logger = logging.getLogger(__name__)

CHECKPOINT_DIR = os.getenv("MODEL_CHECKPOINT_DIR", "/app/checkpoints")


class ClassifyRequest(BaseModel):
    """Request to classify a transaction."""
    description: str
    use_latest_model: bool = True
    model_path: Optional[str] = None


class ClassifyResponse(BaseModel):
    """Classification response."""
    category: str
    confidence: float
    model_used: str


class BatchClassifyRequest(BaseModel):
    """Request to classify multiple transactions."""
    descriptions: List[str]
    use_latest_model: bool = True


class BatchClassifyResponse(BaseModel):
    """Batch classification response."""
    predictions: List[ClassifyResponse]


@router.post("/classify", response_model=ClassifyResponse)
async def classify_transaction(
    request: ClassifyRequest,
    client: Client = Depends(get_user_client),
):
    """
    Classify a single transaction description.
    
    Uses the latest trained model for the user by default.
    """
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        # Determine model path
        if request.use_latest_model:
            model_path = f"{CHECKPOINT_DIR}/{user_id}/latest_checkpoint.pt"
        else:
            model_path = request.model_path
        
        if not model_path or not os.path.exists(model_path):
            raise HTTPException(
                status_code=400,
                detail="No trained model found. Please train a model first.",
            )
        
        # Run classification task synchronously (fast inference)
        result = classify_transaction_task.delay(
            text=request.description,
            model_path=model_path,
            backend_type="cloud",
        ).get(timeout=30)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return ClassifyResponse(
            category=result["category"],
            confidence=result["confidence"],
            model_used=model_path,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(
    request: BatchClassifyRequest,
    client: Client = Depends(get_user_client),
):
    """Classify multiple transactions in batch."""
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        model_path = f"{CHECKPOINT_DIR}/{user_id}/latest_checkpoint.pt"
        
        if not os.path.exists(model_path):
            raise HTTPException(
                status_code=400,
                detail="No trained model found.",
            )
        
        # Process all descriptions
        predictions = []
        for desc in request.descriptions:
            result = classify_transaction_task.delay(
                text=desc,
                model_path=model_path,
                backend_type="cloud",
            ).get(timeout=30)
            
            predictions.append(ClassifyResponse(
                category=result.get("category", "Uncategorized"),
                confidence=result.get("confidence", 0.0),
                model_used=model_path,
            ))
        
        return BatchClassifyResponse(predictions=predictions)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch classification failed: {e}")
        raise HTTPException(status_code=500, detail="Batch classification failed")


@router.get("/models")
async def list_models(client: Client = Depends(get_user_client)):
    """List available trained models for the user."""
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        user_checkpoint_dir = f"{CHECKPOINT_DIR}/{user_id}"
        
        if not os.path.exists(user_checkpoint_dir):
            return {"models": []}
        
        models = []
        for filename in os.listdir(user_checkpoint_dir):
            if filename.endswith(".pt"):
                filepath = os.path.join(user_checkpoint_dir, filename)
                stat = os.stat(filepath)
                models.append({
                    "name": filename,
                    "path": filepath,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "created_at": stat.st_mtime,
                })
        
        return {"models": sorted(models, key=lambda x: x["created_at"], reverse=True)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail="Failed to list models")
