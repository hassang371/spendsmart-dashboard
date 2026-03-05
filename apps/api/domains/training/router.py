"""Training router — upload, train adapter, status, checkpoints.

v2: Trains user's Linear Adapter from categorized transactions,
not the full HypCD pipeline. The frozen MiniLM base model is never retrained.
"""

import hashlib

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from supabase import Client
from typing import Optional

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.domains.ingestion.service import generate_fingerprint
from apps.api.tasks.training_tasks import train_adapter_task
from packages.ingestion_engine.import_transactions import parse_file

router = APIRouter(prefix="/training", tags=["training"])
logger = structlog.get_logger()


def prepare_transaction_payload(row, user_id: str) -> dict:
    """Construct DB payload from a DataFrame row.

    Uses the new unified 6-field fingerprint (BUG-02 fix).
    """
    if isinstance(row["date"], pd.Timestamp):
        date_str = row["date"].strftime("%Y-%m-%d")
    else:
        date_str = str(row["date"])

    amount = float(row["amount"])
    desc = str(row.get("description", ""))
    merchant = str(row.get("merchant", ""))

    fingerprint = generate_fingerprint(
        date=date_str,
        amount=amount,
        merchant=merchant,
        description=desc,
        payment_method=str(row.get("payment_method", "")),
        reference=str(row.get("reference", "")),
    )

    raw_data = {}
    for col in ["method", "entity", "ref", "location", "type", "meta"]:
        if col in row:
            val = row[col]
            raw_data[col] = "" if pd.isna(val) or val is None else val

    return {
        "user_id": user_id,
        "transaction_date": date_str,
        "amount": amount,
        "description": desc,
        "merchant_name": merchant,
        "category": "Uncategorized",
        "type": "debit" if amount < 0 else "credit",
        "fingerprint": fingerprint,
        "raw_data": raw_data,
    }


@router.post("/upload")
async def upload_training_data(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Upload transaction file, ingest into DB, and trigger adapter training."""
    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    # Check duplicates
    try:
        existing = (
            client.table("uploaded_files")
            .select("id")
            .eq("user_id", user_id)
            .eq("file_hash", file_hash)
            .execute()
        )
        if existing.data:
            raise HTTPException(
                status_code=400,
                detail="This file has already been uploaded for training.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("duplicate_check_error", error=str(e))

    # Parse
    try:
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file.")
        df = parse_file(contents, file.filename, password=password)
        if df.empty:
            raise HTTPException(status_code=400, detail="No valid transactions found.")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("parse_failed", error=str(e))
        raise HTTPException(status_code=400, detail="Failed to parse file")

    # Register upload
    try:
        client.table("uploaded_files").insert({
            "user_id": user_id,
            "file_hash": file_hash,
            "filename": file.filename,
            "upload_type": "training",
        }).execute()
    except Exception as e:
        if "duplicate key" in str(e) or "23505" in str(e):
            raise HTTPException(status_code=400, detail="File already uploaded.")
        raise HTTPException(status_code=500, detail="Failed to register upload")

    # Insert transactions
    transactions_to_insert = [
        prepare_transaction_payload(row, user_id)
        for _, row in df.iterrows()
    ]

    try:
        client.table("transactions").upsert(
            transactions_to_insert,
            on_conflict="user_id, fingerprint",
            ignore_duplicates=True,
        ).execute()
    except Exception as e:
        logger.error("db_insert_failed", error=str(e))
        try:
            client.table("uploaded_files").delete().eq(
                "user_id", user_id
            ).eq("file_hash", file_hash).execute()
        except Exception:
            logger.warning("rollback_failed")
        raise HTTPException(status_code=500, detail="Database error")

    # Enqueue training
    try:
        job_data = {
            "user_id": user_id,
            "status": "pending",
            "logs": "Job created via API upload.",
        }
        job_res = client.table("training_jobs").insert(job_data).execute()
        job_id = job_res.data[0]["id"]
    except Exception as e:
        logger.error("job_enqueue_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enqueue training job")

    return {
        "status": "success",
        "message": f"Processed {len(transactions_to_insert)} transactions and queued training.",
        "job_id": job_id,
        "transaction_count": len(transactions_to_insert),
    }


@router.get("/status/{job_id}")
async def get_training_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Get training job status by ID.

    Only returns the job if it belongs to the authenticated user (prevents IDOR).
    """

    try:
        res = (
            client.table("training_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Training job not found")
        return res.data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("status_fetch_failed", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch training status")


@router.get("/latest")
async def get_latest_training_job(
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Get the latest training job for the current user."""
    try:
        res = (
            client.table("training_jobs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error("latest_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch job status")


@router.post("/train")
async def train_adapter_async(
    epochs: int = 5,
    learning_rate: float = 1e-3,
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Start async adapter training job. Returns immediately with job_id.

    v2: Trains the user's Linear Adapter from categorized transactions.
    The frozen MiniLM base model is never retrained.
    """
    try:
        # Fetch user's manually categorized transactions
        res = (
            client.table("transactions")
            .select("description, category")
            .eq("user_id", user_id)
            .eq("is_manual", True)
            .limit(10000)
            .execute()
        )

        if not res.data or len(res.data) < 5:
            raise HTTPException(
                status_code=400,
                detail="Need at least 5 manually categorized transactions for adapter training.",
            )

        texts = [tx["description"] for tx in res.data]
        categories = [tx["category"] for tx in res.data]

        job_data = {
            "user_id": user_id,
            "status": "pending",
            "logs": f"Queued adapter training with {len(res.data)} samples...",
        }
        job_res = client.table("training_jobs").insert(job_data).execute()
        job_id = job_res.data[0]["id"]

        task = train_adapter_task.delay(
            texts=texts,
            categories=categories,
            user_id=user_id,
            job_id=job_id,
            epochs=epochs,
            learning_rate=learning_rate,
        )

        client.table("training_jobs").update({
            "celery_task_id": task.id,
            "status": "queued",
        }).eq("id", job_id).execute()

        return {
            "status": "queued",
            "message": f"Adapter training job queued with {len(res.data)} samples",
            "job_id": job_id,
            "task_id": task.id,
            "epochs": epochs,
            "samples": len(res.data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("train_queue_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to queue training job")
