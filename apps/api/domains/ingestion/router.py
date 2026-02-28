"""Ingestion router — CSV upload and transaction import endpoints.

Absorbs the CSV ingest logic from the old routers/ingestion.py.
Uses the new unified generate_fingerprint (BUG-02 fix).
"""

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from supabase import Client

from apps.api.core.auth import get_user_client
from apps.api.domains.ingestion.service import generate_fingerprint
from packages.ingestion_engine.import_transactions import parse_file

router = APIRouter(prefix="/ingest", tags=["ingestion"])
logger = structlog.get_logger()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    password: str = Form(None),
    client: Client = Depends(get_user_client),
):
    """Accept a CSV or Excel file, parse and fingerprint transactions.

    Uses the centralized ingestion engine for parsing and the new
    unified 6-field fingerprint (BUG-02 fix). Categorization is handled
    separately by the categorization domain.
    """
    # Validate file type
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

    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large (max 10MB)")

        df = parse_file(contents, file.filename, password=password)

        # Drop invalid rows
        if "date" in df.columns:
            df = df.dropna(subset=["date"])
            df = df[df["date"].astype(str).str.strip().ne("")]

        # Replace NaN/inf with None for JSON safety
        import numpy as np
        df = df.replace([np.nan, np.inf, -np.inf], None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("file_parse_failed", error=str(e), filename=filename)
        raise HTTPException(status_code=400, detail="Failed to parse file")

    # Build transactions with unified fingerprint
    transactions = []
    for _, row in df.iterrows():
        tx = row.to_dict()
        tx["fingerprint"] = generate_fingerprint(
            date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0)),
            merchant=str(tx.get("merchant", "")),
            description=str(tx.get("description", "")),
            payment_method=str(tx.get("payment_method", "")),
            reference=str(tx.get("reference", "")),
        )
        transactions.append(tx)

    logger.info("ingest_complete", count=len(transactions), filename=filename)
    return {"transactions": transactions, "count": len(transactions)}
