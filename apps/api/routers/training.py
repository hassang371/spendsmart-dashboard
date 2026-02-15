from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    Depends,
    HTTPException,
)
from typing import Optional
from packages.ingestion_engine.import_transactions import (
    parse_file,
    generate_fingerprint,
)
from apps.api.deps import get_user_client
from apps.api.tasks.training_tasks import train_model_task
from supabase import Client
import pandas as pd
import logging

router = APIRouter(tags=["training"])
logger = logging.getLogger(__name__)


def prepare_transaction_payload(row, user_id: str):
    """
    Constructs the DB payload from a DataFrame row, including structured metadata.
    """
    # Clean row data
    if isinstance(row["date"], pd.Timestamp):
        date_str = row["date"].strftime("%Y-%m-%d")
    else:
        date_str = str(row["date"])

    amount = float(row["amount"])
    desc = str(row["description"])
    merchant = str(row["merchant"])

    fingerprint = generate_fingerprint(date_str, amount, merchant)

    # Extract structured fields if available
    raw_data = {}
    structured_cols = ["method", "entity", "ref", "location", "type", "meta"]
    for col in structured_cols:
        if col in row:
            val = row[col]
            # Handle NaN/None
            if pd.isna(val) or val is None:
                raw_data[col] = ""
            else:
                raw_data[col] = val

    return {
        "user_id": user_id,
        "transaction_date": date_str,
        "amount": amount,
        "description": desc,
        "merchant_name": merchant,
        "category": "Uncategorized",  # Default
        "type": "expense" if amount < 0 else "income",
        "fingerprint": fingerprint,
        "raw_data": raw_data,  # Store structured metadata here
    }


@router.post("/training/upload")
async def upload_training_data(
    file: UploadFile = File(...),
    password: Optional[str] = Form(None),
    client: Client = Depends(get_user_client),
):
    """
    Uploads a transaction file (CSV/Excel), ingests it into Supabase,
    and triggers a model training job.
    """
    # 0. Check for Duplicates (Quick Check)
    import hashlib

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    user_id = user_response.user.id

    # Check if hash exists for this user WITHOUT inserting yet
    try:
        existing = (
            client.table("uploaded_files")
            .select("id")
            .eq("user_id", user_id)
            .eq("file_hash", file_hash)
            .execute()
        )
        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=400,
                detail="This file has already been uploaded for training.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking duplicate: {e}")

    # 1. Parse (Fail Fast)
    try:
        if not contents:
            raise HTTPException(status_code=400, detail="Empty file.")

        df = parse_file(contents, file.filename, password=password)

        if df.empty:
            raise HTTPException(
                status_code=400, detail="No valid transactions found in file."
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to parse file")

    # 2. Insert into uploaded_files (Commit Point 1)
    try:
        client.table("uploaded_files").insert(
            {
                "user_id": user_id,
                "file_hash": file_hash,
                "filename": file.filename,
                "upload_type": "training",
            }
        ).execute()
    except Exception as e:
        # If insert fails now (e.g. race condition), it's a duplicate
        if "duplicate key" in str(e) or "23505" in str(e):
            raise HTTPException(
                status_code=400,
                detail="This file has already been uploaded for training.",
            )
        raise HTTPException(status_code=500, detail="Failed to register upload")

    # 3. Prepare for DB Insert
    transactions_to_insert = []

    for _, row in df.iterrows():
        tx = prepare_transaction_payload(row, user_id)
        transactions_to_insert.append(tx)

    # 4. Insert into Supabase 'transactions'
    try:
        client.table("transactions").upsert(
            transactions_to_insert,
            on_conflict="user_id, fingerprint",
            ignore_duplicates=True,
        ).execute()

    except Exception as e:
        logger.error(f"DB Insert failed: {e}")
        # Ideally rollback uploaded_files here, but minimal impact if we don't.
        # The file is "uploaded" but transactions failed.
        # User can retry -> will fail duplicate check? Yes.
        # So we SHOULD delete from uploaded_files if this fails.
        try:
            client.table("uploaded_files").delete().eq("user_id", user_id).eq(
                "file_hash", file_hash
            ).execute()
        except Exception:
            logger.warning("Rollback of uploaded_files failed", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error")

    # 5. Enqueue Training Job
    try:
        job_data = {
            "user_id": user_id,
            "status": "pending",
            "logs": "Job created via API upload.",
        }
        job_res = client.table("training_jobs").insert(job_data).execute()
        job_id = job_res.data[0]["id"]
    except Exception as e:
        logger.error(f"Job enqueue failed: {e}")
        # Only partial rollback? Transactions are good, just job failed.
        # Let's keep transactions but fail the request? Or return warning?
        # User expects training. If training fails to start, it's an error.
        raise HTTPException(
            status_code=500, detail="Failed to enqueue training job"
        )

    return {
        "status": "success",
        "message": f"Processed {len(transactions_to_insert)} transactions and queued training.",
        "job_id": job_id,
        "transaction_count": len(transactions_to_insert),
    }


@router.get("/training/status/{job_id}")
async def get_training_status(job_id: str, client: Client = Depends(get_user_client)):
    # ... existing implementation ...
    try:
        res = (
            client.table("training_jobs")
            .select("*")
            .eq("id", job_id)
            .single()
            .execute()
        )
        return res.data
    except Exception as e:
        logger.error(f"Failed to fetch training status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch training status")


@router.get("/training/latest")
async def get_latest_training_job(client: Client = Depends(get_user_client)):
    """
    Get the latest training job for the current user.
    """
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id

        # Select latest job created by user
        res = (
            client.table("training_jobs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not res.data:
            return None

        return res.data[0]
    except Exception as e:
        logger.error(f"Failed to fetch latest job: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch job status")


@router.post("/train")
async def train_model_async(
    epochs: int = 10,
    batch_size: int = 32,
    learning_rate: float = 1e-4,
    client: Client = Depends(get_user_client),
):
    """
    Start async training job for HypCD model.
    
    Returns immediately with job_id. Check status via /training/status/{job_id}.
    """
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        user_id = user_response.user.id
        
        # Fetch user's labeled transactions
        res = (
            client.table("transactions")
            .select("description, category")
            .eq("user_id", user_id)
            .not_.is_("category", None)
            .execute()
        )
        
        if not res.data or len(res.data) < 10:
            raise HTTPException(
                status_code=400,
                detail="Need at least 10 labeled transactions for training.",
            )
        
        # Prepare data
        texts = [tx["description"] for tx in res.data]
        
        # Map categories to labels
        from packages.categorization.constants import CATEGORIES
        category_to_idx = {cat: idx for idx, cat in enumerate(CATEGORIES)}
        labels = [category_to_idx.get(tx["category"], 0) for tx in res.data]
        
        # Create training job record
        job_data = {
            "user_id": user_id,
            "status": "pending",
            "logs": f"Queued training with {len(res.data)} samples...",
        }
        job_res = client.table("training_jobs").insert(job_data).execute()
        job_id = job_res.data[0]["id"]
        
        # Queue async training task
        task = train_model_task.delay(
            texts=texts,
            labels=labels,
            user_id=user_id,
            job_id=job_id,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
        )
        
        # Update job with task_id
        client.table("training_jobs").update({
            "celery_task_id": task.id,
            "status": "queued",
        }).eq("id", job_id).execute()
        
        return {
            "status": "queued",
            "message": f"Training job queued with {len(res.data)} samples",
            "job_id": job_id,
            "task_id": task.id,
            "epochs": epochs,
            "samples": len(res.data),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to queue training: {e}")
        raise HTTPException(status_code=500, detail="Failed to queue training job")
