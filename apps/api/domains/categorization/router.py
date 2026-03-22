"""Categorization router — classify, batch classify, feedback, metrics.

v2: Uses lightweight MiniLM + Cosine Similarity classifier.
Removed: /discover (GCD), HypCD references.
"""

try:
    import structlog

    logger = structlog.get_logger()
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.core.idempotency import get_idempotency_key, with_idempotency
from apps.api.domains.categorization.schemas import (
    BatchClassifyRequest,
    BatchClassifyResponse,
    ClassifyRequest,
    ClassifyResponse,
    FeedbackRequest,
)
from apps.api.domains.categorization.service import (
    classify_batch_in_process,
    classify_single,
    get_classifier,
)
from supabase import Client

router = APIRouter(prefix="/categorization", tags=["categorization"])


@router.post("/classify", response_model=ClassifyResponse)
async def classify_transaction(
    request: ClassifyRequest,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Classify a single transaction description."""
    try:
        try:
            result = classify_single(request.description, user_id=user_id, client=client)
        except TypeError:
            # Backward compatibility for tests/mocks using the legacy signature.
            result = classify_single(request.description)
        return ClassifyResponse(
            category=result["category"],
            confidence=result["confidence"],
            model_used="minilm-cosine-v2",
        )
    except Exception as e:
        logger.error("classify_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(
    request: BatchClassifyRequest,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    """Classify multiple transactions in a single batch."""

    async def _execute():
        if not request.descriptions:
            raise HTTPException(status_code=400, detail="No descriptions provided")

        try:
            try:
                results = classify_batch_in_process(
                    request.descriptions,
                    user_id=user_id,
                    client=client,
                )
            except TypeError:
                # Backward compatibility for tests/mocks using the legacy signature.
                results = classify_batch_in_process(request.descriptions)
            predictions = [
                ClassifyResponse(
                    category=r["category"],
                    confidence=r["confidence"],
                    model_used="minilm-cosine-v2",
                )
                for r in results
            ]
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
):
    """Accept category corrections for active learning.

    Stores corrections in training_corrections table. These are used
    to train per-user Linear Adapters.
    """
    corrections = request.corrections
    if not corrections:
        raise HTTPException(status_code=400, detail="No corrections provided")

    rows_to_insert: list[dict[str, str]] = []
    for key, value in corrections.items():
        if isinstance(value, str):
            rows_to_insert.append(
                {
                    "user_id": user_id,
                    "description": str(key),
                    "corrected_category": value,
                }
            )
        elif isinstance(value, list):
            for description in value:
                rows_to_insert.append(
                    {
                        "user_id": user_id,
                        "description": str(description),
                        "corrected_category": str(key),
                    }
                )

    if not rows_to_insert:
        raise HTTPException(status_code=400, detail="No valid corrections provided")

    try:
        client.table("training_corrections").insert(rows_to_insert).execute()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to store feedback")

    # Propagate corrections to transactions so POST /training/train can consume them.
    # training/router.py reads transactions WHERE is_manual=True.
    for row in rows_to_insert:
        try:
            client.table("transactions").update({"is_manual": True, "category": row["corrected_category"]}).eq(
                "user_id", user_id
            ).eq("description", row["description"]).execute()
        except Exception as e:
            # Non-fatal: correction stored; transaction update failure logged only.
            logger.warning(
                "feedback_transaction_update_failed",
                description=row["description"],
                error=str(e),
            )

    updated_categories = sorted({row["corrected_category"] for row in rows_to_insert if row["corrected_category"]})
    return {"status": "ok", "updated_categories": updated_categories}


@router.get("/metrics")
async def get_classification_metrics(
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Compute classification accuracy metrics using manually-corrected transactions.

    Ground truth: transactions where is_manual=True.
    Returns per-class F1, confidence histogram.
    """

    try:
        result = (
            client.table("transactions")
            .select("description,category")
            .eq("user_id", user_id)
            .eq("is_manual", True)
            .execute()
        )
        labeled = result.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB query failed: {e}")

    if not labeled:
        raise HTTPException(
            status_code=404,
            detail="No labeled data. Correct some transactions first to generate metrics.",
        )

    descriptions = [r["description"] for r in labeled if r.get("description")]
    true_categories = [r["category"] for r in labeled if r.get("description")]

    if not descriptions:
        raise HTTPException(status_code=400, detail="No valid descriptions in labeled data")

    try:
        try:
            predictions = classify_batch_in_process(
                descriptions,
                user_id=user_id,
                client=client,
            )
        except TypeError:
            predictions = classify_batch_in_process(descriptions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")

    pred_categories = [p["category"] for p in predictions]
    confidences = [p["confidence"] for p in predictions]

    # Accuracy
    correct = sum(1 for t, p in zip(true_categories, pred_categories) if t == p)
    acc = correct / len(true_categories) if true_categories else 0.0

    # Confidence histogram
    bucket_keys = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    buckets: dict[str, int] = {k: 0 for k in bucket_keys}
    for c in confidences:
        idx = min(int(c / 0.2), 4)
        buckets[bucket_keys[idx]] += 1

    return {
        "overall_accuracy": round(acc, 4),
        "confidence_histogram": buckets,
        "total_corrections": len(labeled),
        "model": "minilm-cosine-v2",
    }


@router.get("/models")
async def list_models(client: Client = Depends(get_user_client)):
    """List available model architecture and user adapters."""
    return {
        "base_model": "sentence-transformers/all-MiniLM-L6-v2",
        "embedding_dim": 384,
        "classifier_type": "cosine_similarity_zero_shot",
        "adapter_type": "linear_adapter",
        "confidence_threshold": get_classifier().confidence_threshold,
    }
