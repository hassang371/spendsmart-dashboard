"""Categorization router — thin HTTP layer delegating to CategorizationService.

Refs: docs/features/012-categorization-service-deepening.md
"""

try:
    import structlog

    logger = structlog.get_logger()
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, Request

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.core.idempotency import get_idempotency_key, with_idempotency
from apps.api.domains.categorization.schemas import (
    BatchClassifyRequest,
    BatchClassifyResponse,
    ClassifyRequest,
    ClassifyResponse,
    FeedbackRequest,
)
from apps.api.domains.categorization.service import CategorizationService
from supabase import Client

router = APIRouter(prefix="/categorization", tags=["categorization"])


def get_categorization_service(request: Request) -> CategorizationService:
    return request.app.state.categorization_service


@router.post("/classify", response_model=ClassifyResponse)
async def classify_transaction(
    request: ClassifyRequest,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    service: CategorizationService = Depends(get_categorization_service),
):
    try:
        result = service.classify(request.description, user_id=user_id, client=client)
        return ClassifyResponse(category=result.category, confidence=result.confidence)
    except Exception as e:
        logger.error("classify_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(
    request: BatchClassifyRequest,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    idempotency_key: str | None = Depends(get_idempotency_key),
    service: CategorizationService = Depends(get_categorization_service),
):
    async def _execute():
        if not request.descriptions:
            raise HTTPException(status_code=400, detail="No descriptions provided")
        try:
            results = service.classify_batch(request.descriptions, user_id=user_id, client=client)
            predictions = [ClassifyResponse(category=r.category, confidence=r.confidence) for r in results]
            return BatchClassifyResponse(predictions=predictions)
        except Exception as e:
            logger.error("batch_classify_failed", error=str(e), count=len(request.descriptions))
            raise HTTPException(status_code=500, detail="Batch classification failed")

    return await with_idempotency(idempotency_key, _execute)


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    service: CategorizationService = Depends(get_categorization_service),
):
    if not request.corrections:
        raise HTTPException(status_code=400, detail="No corrections provided")
    try:
        result = service.store_feedback(request.corrections, user_id=user_id, client=client)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to store feedback")

    if result.stored_count == 0:
        raise HTTPException(status_code=400, detail="No valid corrections provided")

    if result.transaction_sync_failed:
        logger.warning("feedback_transaction_sync_partial", user_id=user_id)

    return {"status": "ok", "updated_categories": result.updated_categories}


@router.get("/metrics")
async def get_classification_metrics(
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    service: CategorizationService = Depends(get_categorization_service),
):
    try:
        result = service.compute_metrics(user_id=user_id, client=client)
    except ValueError as e:
        if "no_labeled_data" in str(e):
            raise HTTPException(
                status_code=404,
                detail="No labeled data. Correct some transactions first to generate metrics.",
            )
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB query failed: {e}")

    return {
        "overall_accuracy": result.overall_accuracy,
        "confidence_histogram": result.confidence_histogram,
        "total_corrections": result.total_corrections,
        "model": result.model,
    }


@router.get("/models")
async def list_models(
    service: CategorizationService = Depends(get_categorization_service),
):
    return {
        "base_model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dim": 384,
        "classifier_type": "cosine_similarity_zero_shot",
        "adapter_type": "linear_adapter",
        "confidence_threshold": service.confidence_threshold,
    }
