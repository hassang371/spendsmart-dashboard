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


@router.get("/metrics")
async def get_classification_metrics(client: Client = Depends(get_user_client)):
    """Compute classification accuracy metrics using manually-corrected transactions.

    Ground truth: transactions where is_manual=True.
    Returns per-class F1, confidence histogram, and rule vs. model split.
    Requires at least 1 manually corrected transaction.
    """
    from sklearn.metrics import accuracy_score, precision_recall_fscore_support
    import numpy as np

    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id

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
        predictions = classify_batch_in_process(descriptions)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")

    pred_categories = [p["category"] for p in predictions]
    confidences = [p["confidence"] for p in predictions]
    paths = [p.get("path", "unknown") for p in predictions]

    classifier = get_classifier()
    label_names = classifier.labels
    label2idx = {label: i for i, label in enumerate(label_names)}

    y_true = np.array([label2idx.get(c, len(label_names) - 1) for c in true_categories])
    y_pred = np.array([label2idx.get(c, len(label_names) - 1) for c in pred_categories])

    acc = float(accuracy_score(y_true, y_pred))
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred,
        labels=list(range(len(label_names))),
        zero_division=0,
    )

    per_class = {
        label_names[i]: {
            "precision": float(precision[i]),
            "recall":    float(recall[i]),
            "f1":        float(f1[i]),
            "support":   int(support[i]),
        }
        for i in range(len(label_names))
        if support[i] > 0
    }

    bucket_keys = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    buckets: dict[str, int] = {k: 0 for k in bucket_keys}
    for c in confidences:
        idx = min(int(c / 0.2), 4)
        buckets[bucket_keys[idx]] += 1

    split: dict[str, int] = {"keyword_rule": 0, "hypffn": 0, "novel_cluster": 0}
    for p in paths:
        if p in split:
            split[p] += 1
        else:
            split["hypffn"] += 1

    return {
        "overall_accuracy": acc,
        "per_class": per_class,
        "confidence_histogram": buckets,
        "rule_vs_model_split": split,
        "total_corrections": len(labeled),
        "novel_categories_discovered": sum(1 for p in predictions if p.get("is_novel")),
    }


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
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": stat.st_mtime,
            })

    return {"models": sorted(models, key=lambda x: x["created_at"], reverse=True)}
