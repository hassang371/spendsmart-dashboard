"""Categorization router — classify, batch classify, feedback, discover.

Consolidates endpoints from old routers/ingestion.py and routers/classify.py.

Fixes:
- BUG-03: Single /classify endpoint (no more shadow conflict).
- BUG-04: Batch classify runs in-process (no N+1 Celery).
- ARCH-04: Classifier singleton via service module.
- IMP-04: All endpoints use Pydantic schemas.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from apps.api.core.auth import get_user_client
from apps.api.domains.categorization.schemas import (
    BatchClassifyRequest,
    BatchClassifyResponse,
    ClassifyRequest,
    ClassifyResponse,
    DiscoverRequest,
    FeedbackRequest,
)
from apps.api.domains.categorization.service import (
    classify_batch_in_process,
    classify_single_in_process,
    get_classifier,
)

router = APIRouter(prefix="/categorization", tags=["categorization"])
logger = structlog.get_logger()


@router.post("/classify", response_model=ClassifyResponse)
async def classify_transaction(
    request: ClassifyRequest,
    client: Client = Depends(get_user_client),
):
    """Classify a single transaction description.

    BUG-03 fix: This is the ONLY /classify endpoint. The old codebase had
    two conflicting routes registered under the same path.
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    try:
        result = classify_single_in_process(request.description)
        return ClassifyResponse(
            category=result["category"],
            confidence=result["confidence"],
            model_used="hypcd",
        )
    except Exception as e:
        logger.error("classify_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Classification failed")


@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_batch(
    request: BatchClassifyRequest,
    client: Client = Depends(get_user_client),
):
    """Classify multiple transactions in a single batch.

    BUG-04 fix: Runs inference in-process instead of dispatching N separate
    Celery tasks with .delay().get() on each one.
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    if not request.descriptions:
        raise HTTPException(status_code=400, detail="No descriptions provided")

    try:
        results = classify_batch_in_process(request.descriptions)
        predictions = [
            ClassifyResponse(
                category=r["category"],
                confidence=r["confidence"],
                model_used="hypcd",
            )
            for r in results
        ]
        return BatchClassifyResponse(predictions=predictions)
    except Exception as e:
        logger.error("batch_classify_failed", error=str(e), count=len(request.descriptions))
        raise HTTPException(status_code=500, detail="Batch classification failed")


@router.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    client: Client = Depends(get_user_client),
):
    """Accept category corrections for active learning."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    corrections = request.corrections
    if not corrections:
        raise HTTPException(status_code=400, detail="No corrections provided")

    rows_to_insert: list[dict[str, str]] = []
    for key, value in corrections.items():
        if isinstance(value, str):
            rows_to_insert.append({
                "user_id": user_response.user.id,
                "description": str(key),
                "corrected_category": value,
            })
        elif isinstance(value, list):
            for description in value:
                rows_to_insert.append({
                    "user_id": user_response.user.id,
                    "description": str(description),
                    "corrected_category": str(key),
                })

    if not rows_to_insert:
        raise HTTPException(status_code=400, detail="No valid corrections provided")

    try:
        client.table("training_corrections").insert(rows_to_insert).execute()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to store feedback")

    updated_categories = sorted(
        {row["corrected_category"] for row in rows_to_insert if row["corrected_category"]}
    )
    return {"status": "ok", "updated_categories": updated_categories}


@router.post("/discover")
async def discover_categories(
    request: DiscoverRequest,
    client: Client = Depends(get_user_client),
):
    """Discover novel categories using Generalized Category Discovery."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    if not request.descriptions:
        raise HTTPException(status_code=400, detail="No descriptions provided")

    if len(request.descriptions) < request.n_clusters * 2:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {request.n_clusters * 2} descriptions",
        )

    try:
        classifier = get_classifier()
        if not hasattr(classifier, "discover_categories"):
            raise HTTPException(
                status_code=501,
                detail="GCD not available with current classifier version",
            )

        discovered = classifier.discover_categories(
            texts=request.descriptions,
            n_clusters=request.n_clusters,
            confidence_threshold=request.confidence_threshold,
        )

        for cat in discovered:
            if hasattr(cat.get("centroid"), "tolist"):
                cat["centroid"] = cat["centroid"].tolist()

        return {
            "discovered_categories": discovered,
            "total_descriptions": len(request.descriptions),
            "n_clusters": request.n_clusters,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("gcd_failed", error=str(e))
        raise HTTPException(status_code=500, detail="GCD failed")


@router.get("/models")
async def list_models(client: Client = Depends(get_user_client)):
    """List available trained models for the user."""
    import os

    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    checkpoint_dir = os.getenv("MODEL_CHECKPOINT_DIR", "/app/checkpoints")
    user_dir = f"{checkpoint_dir}/{user_response.user.id}"

    if not os.path.exists(user_dir):
        return {"models": []}

    models = []
    for filename in os.listdir(user_dir):
        if filename.endswith(".pt"):
            filepath = os.path.join(user_dir, filename)
            stat = os.stat(filepath)
            models.append({
                "name": filename,
                "path": filepath,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": stat.st_mtime,
            })

    return {"models": sorted(models, key=lambda x: x["created_at"], reverse=True)}
