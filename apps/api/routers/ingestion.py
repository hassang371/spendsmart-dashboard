"""CSV ingestion endpoint — parses and fingerprints uploaded transactions."""

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from supabase import Client

from apps.api.deps import get_user_client
from packages.ingestion_engine.import_transactions import (
    generate_fingerprint,
    parse_file,
)
from packages.categorization.hypcd import HypCDClassifier

router = APIRouter(tags=["ingestion"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMITS_PER_MINUTE = {
    "ingest": 20,
    "classify": 120,
    "feedback": 60,
    "discover": 30,
}
_request_windows: dict[tuple[str, str], deque[float]] = defaultdict(deque)

def get_classifier():
    return HypCDClassifier()


def enforce_rate_limit(user_id: str, operation: str) -> None:
    limit = RATE_LIMITS_PER_MINUTE.get(operation, 60)
    key = (user_id, operation)
    window = _request_windows[key]
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS

    while window and window[0] < cutoff:
        window.popleft()

    if len(window) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    window.append(now)


@router.post("/ingest/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    password: str = Form(None),
    client: Client = Depends(get_user_client),
):
    """
    Accept a CSV or Excel file, parse it through the ingestion engine,
    categorize transactions using HypCD,
    and return fingerprinted + categorized transactions.
    """
    # Validate file type by extension
    allowed_extensions = (".csv", ".tsv", ".xls", ".xlsx", ".xlsm", ".json", ".txt")
    filename = file.filename or ""
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Accepted: {', '.join(allowed_extensions)}",
        )

    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    enforce_rate_limit(user_response.user.id, "ingest")

    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large")
        # Use centralized parser (handles CSV, Excel, password)
        df = parse_file(contents, file.filename, password=password)

        # Clean NaN/inf values that break JSON serialization
        # Drop rows with NaN dates (footer/junk rows from bank statements)
        if "date" in df.columns:
            df = df.dropna(subset=["date"])
            df = df[df["date"].astype(str).str.strip().ne("")]

        # Replace remaining NaN/inf with None for JSON safety
        import numpy as np

        df = df.replace([np.nan, np.inf, -np.inf], None)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse file")

    # 1. Extract texts for batch categorization
    # Use description for better context (Cleaner & Rules work on raw text)
    if "description" in df.columns:
        texts_to_classify = df["description"].fillna("").astype(str).tolist()
    else:
        texts_to_classify = df["merchant"].fillna("Unknown").astype(str).tolist()

    # 2. Run HypCD
    classifier = get_classifier()
    # returns list of (category, confidence, embedding)
    predictions = classifier.predict_batch(texts_to_classify)

    categories = [
        p.get("category", "Misc") if isinstance(p, dict) else p[0] for p in predictions
    ]
    confidences = [
        p.get("confidence", 0.0) if isinstance(p, dict) else p[1] for p in predictions
    ]

    # 3. Add to DataFrame (optional, but good for debugging)
    df["category"] = categories
    df["category_confidence"] = confidences

    # Generate fingerprints and build response
    transactions = []
    for _, row in df.iterrows():
        tx = row.to_dict()
        # Generate fingerprint from date + amount + merchant
        tx["fingerprint"] = generate_fingerprint(
            iso_date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0)),
            merchant=str(tx.get("merchant", "")),
        )
        # Ensure category is in the dict (pandas might use numpy types, cast to native)
        tx["category"] = str(row["category"])
        # API Schema might not expect confidence, so maybe keep it internal or check schema

        transactions.append(tx)

    return {"transactions": transactions, "count": len(transactions)}


@router.post("/classify")
async def classify_descriptions(body: dict, client: Client = Depends(get_user_client)):
    """
    Accept a list of transaction descriptions and return predicted categories.
    Used by the frontend to classify transactions at import time.
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    enforce_rate_limit(user_response.user.id, "classify")

    descriptions = body.get("descriptions", [])
    if not descriptions:
        raise HTTPException(status_code=400, detail="No descriptions provided")
    classifier = get_classifier()
    predictions = classifier.predict_batch(descriptions)
    result: dict[str, str] = {}
    for desc, pred in zip(descriptions, predictions):
        if isinstance(pred, dict):
            result[desc] = str(pred.get("category", "Misc"))
        else:
            result[desc] = str(pred[0])
    return result


@router.post("/feedback")
async def submit_feedback(body: dict, client: Client = Depends(get_user_client)):
    """
    Accept category corrections and update HypCD anchors for active learning.
    Format: {"corrections": {"description": "NewCategory", ...}}
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    enforce_rate_limit(user_response.user.id, "feedback")

    corrections = body.get("corrections", {})
    if not corrections:
        raise HTTPException(status_code=400, detail="No corrections provided")

    rows_to_insert: list[dict[str, str]] = []

    for key, value in corrections.items():
        if isinstance(value, str):
            rows_to_insert.append(
                {
                    "user_id": user_response.user.id,
                    "description": str(key),
                    "corrected_category": value,
                }
            )
        elif isinstance(value, list):
            for description in value:
                rows_to_insert.append(
                    {
                        "user_id": user_response.user.id,
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

    updated_categories = sorted(
        {row["corrected_category"] for row in rows_to_insert if row["corrected_category"]}
    )
    return {"status": "ok", "updated_categories": updated_categories}


@router.post("/discover")
async def discover_categories(body: dict, client: Client = Depends(get_user_client)):
    """
    Discover novel categories using Generalized Category Discovery (GCD).

    Accepts unlabeled transaction descriptions and returns discovered clusters
    that don't match existing categories.

    Request body:
        {
            "descriptions": ["unknown transaction 1", "unknown transaction 2", ...],
            "n_clusters": 5,
            "confidence_threshold": 0.7
        }

    Returns:
        {
            "discovered_categories": [
                {
                    "cluster_id": 0,
                    "sample_texts": ["...", "..."],
                    "confidence": 0.85,
                    "count": 12
                },
                ...
            ]
        }
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    enforce_rate_limit(user_response.user.id, "discover")

    descriptions = body.get("descriptions", [])
    n_clusters = body.get("n_clusters", 5)
    confidence_threshold = body.get("confidence_threshold", 0.7)

    if not descriptions:
        raise HTTPException(status_code=400, detail="No descriptions provided")

    if len(descriptions) < n_clusters * 2:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {n_clusters * 2} descriptions to discover {n_clusters} categories",
        )

    try:
        classifier = get_classifier()

        # Check if classifier has discover_categories method
        if not hasattr(classifier, "discover_categories"):
            raise HTTPException(
                status_code=501,
                detail="GCD not available with current classifier version",
            )

        discovered = classifier.discover_categories(
            texts=descriptions,
            n_clusters=n_clusters,
            confidence_threshold=confidence_threshold,
        )

        # Convert tensor centroids to lists for JSON serialization
        for cat in discovered:
            if hasattr(cat["centroid"], "tolist"):
                cat["centroid"] = cat["centroid"].tolist()

        return {
            "discovered_categories": discovered,
            "total_descriptions": len(descriptions),
            "n_clusters": n_clusters,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="GCD failed")
