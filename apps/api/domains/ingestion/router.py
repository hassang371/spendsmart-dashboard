"""Ingestion router — file upload and transaction import endpoints.

v3 Architecture: Insert-first, classify-later.
- Parse file → insert ALL rows as Uncategorized via single Supabase RPC
- ON CONFLICT (user_id, fingerprint) handles dedup at DB level
- Background task classifies and updates categories progressively
- For files >5K rows, priority insert (first 100 by date) + background rest
"""

import asyncio
import hashlib
import time
import structlog
import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from supabase import Client
from apps.api.core.idempotency import get_idempotency_key, with_idempotency

from apps.api.core.auth import get_current_user_id, get_user_client
from packages.ingestion_engine.import_transactions import parse_file
from apps.api.domains.ingestion.service import generate_fingerprint
from packages.ingestion_engine.merchant_extractor import MerchantExtractor, infer_payment_method
from packages.categorization.cleaner import process_description

_merchant_extractor = MerchantExtractor()  # module-level singleton

router = APIRouter(prefix="/ingest", tags=["ingestion"])
logger = structlog.get_logger()

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB
MAX_RPC_BATCH = 5000  # Max rows per single RPC call
PRIORITY_THRESHOLD = 5000  # Files larger than this use priority insert


def _build_transaction_row(row: dict, user_id: str, fingerprint: str) -> dict:
    """Build a Supabase-ready transaction row from a parsed row.

    Always sets category to 'Uncategorized' — classification happens async.
    """
    amount = float(row.get("amount", 0) or 0)
    tx_type = "credit" if amount >= 0 else "debit"
    description = str(row.get("description", "") or "")

    # Process description through v2 cleaner for informative text, merchant, bank
    processed = process_description(description)
    informative_text = processed.informative
    bank_name = processed.bank_name

    # Use CSV-provided merchant name, fall back to cleaner, then extractor
    raw_merchant = str(row.get("merchant", "") or "").strip()
    merchant_name = raw_merchant or processed.merchant_name or _merchant_extractor.extract(description)

    # Use CSV-provided payment method, fall back to inference
    raw_payment = str(row.get("payment_method", "") or "").strip()
    payment_method = raw_payment if raw_payment else infer_payment_method(description)

    # Cancelled transactions (zero amount)
    status = "cancelled" if amount == 0 else str(row.get("status", "completed") or "completed")

    return {
        "transaction_date": str(row.get("date", "")),
        "amount": amount,
        "currency": str(row.get("currency", "INR") or "INR"),
        "description": description,
        "merchant_name": merchant_name,
        "payment_method": payment_method,
        "status": status,
        "type": tx_type,
        "fingerprint": fingerprint,
        "informative_text": informative_text,
        "bank_name": bank_name,
        "raw_data": {
            k: (None if (v is None or (isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf"))))
                else str(v) if hasattr(v, "isoformat") else v)
            for k, v in row.items()
        },

    }


def _rpc_insert_batch(client: Client, user_id: str, rows: list[dict]) -> tuple[int, int]:
    """Insert a batch of rows via the batch_import_transactions RPC.

    Returns (inserted_count, skipped_count).
    Pass rows as a native Python list — PostgREST serialises it to JSONB correctly.
    Passing json.dumps() would send a text scalar and trigger 'cannot get array length of a scalar'.
    """
    result = client.rpc("batch_import_transactions", {
        "p_user_id": user_id,
        "p_rows": rows,  # NOT json.dumps — let PostgREST handle JSONB serialization
    }).execute()

    if result.data:
        row = result.data[0] if isinstance(result.data, list) else result.data
        return int(row.get("inserted_count", 0)), int(row.get("skipped_count", 0))
    return 0, 0


def _insert_remaining_rows(user_id: str, rows: list[dict], token: str, job_id: str | None) -> None:
    """Background task: insert remaining rows from large-file priority insert.

    Called only when file has >PRIORITY_THRESHOLD rows and the first 100
    were already inserted synchronously. Runs alongside classification.
    """
    if not rows:
        return
    try:
        from supabase import create_client
        from apps.api.core.auth import _get_supabase_url, _get_supabase_anon_key
        client = create_client(_get_supabase_url(), _get_supabase_anon_key())
        client.postgrest.auth(token)

        total_ins = 0
        total_skip = 0
        for i in range(0, len(rows), MAX_RPC_BATCH):
            chunk = rows[i:i + MAX_RPC_BATCH]
            ins, skip = _rpc_insert_batch(client, user_id, chunk)
            total_ins += ins
            total_skip += skip

        logger.info(
            "bg_bulk_insert_complete",
            user_id=user_id,
            inserted=total_ins,
            skipped=total_skip,
        )
    except Exception as e:
        logger.warning("bg_bulk_insert_failed", user_id=user_id, error=str(e))


def _classify_descriptions(descriptions: list[str]) -> dict[str, dict]:
    """Classify transaction descriptions using MiniLM + Cosine Similarity."""
    result: dict[str, dict] = {}
    if not descriptions:
        return result

    try:
        from apps.api.domains.categorization.service import classify_batch_in_process
        classifications = classify_batch_in_process(descriptions)
        for desc, clf in zip(descriptions, classifications):
            result[desc] = {
                "category":   clf.get("category", "Uncategorized"),
                "confidence": float(clf.get("confidence", 0.0)),
            }
        return result
    except Exception as e:
        logger.warning("classifier_unavailable_for_import", error=str(e))

    # Fallback: keyword matcher
    from packages.categorization.rules import KeywordMatcher
    matcher = KeywordMatcher()
    for desc in descriptions:
        match = matcher.predict(desc)
        result[desc] = match if match else {"category": "Uncategorized", "confidence": 0.0}

    return result


def _classify_and_update_transactions(
    user_id: str, fps_to_desc: dict, token: str, job_id: str | None = None
) -> None:
    """Background task: classify inserted transactions and update categories.

    Uses import_jobs table for status tracking.
    Only updates rows still marked as 'Uncategorized' (won't overwrite user edits).
    """
    from packages.categorization.classifier import CONFIDENCE_THRESHOLD

    unique_descs = list({desc for desc in fps_to_desc.values() if desc.strip()})
    if not unique_descs:
        return

    try:
        category_map = _classify_descriptions(unique_descs)
    except Exception as e:
        logger.warning("bg_classify_failed", error=str(e))
        return

    # Separate confident vs uncertain predictions
    confident_fps: dict[str, list[str]] = defaultdict(list)
    uncertain_rows: list[dict] = []

    for fp, desc in fps_to_desc.items():
        pred = category_map.get(desc, {"category": "Uncategorized", "confidence": 0.0})
        cat = pred["category"]
        conf = pred["confidence"]

        if conf >= CONFIDENCE_THRESHOLD and cat != "Uncategorized":
            confident_fps[cat].append(fp)
        else:
            uncertain_rows.append({"fp": fp, "suggested": cat, "confidence": conf})

    try:
        from supabase import create_client
        from apps.api.core.auth import _get_supabase_url, _get_supabase_anon_key
        client = create_client(_get_supabase_url(), _get_supabase_anon_key())
        client.postgrest.auth(token)

        CHUNK_SIZE = 50
        classified = 0

        # Update confident predictions — only rows still Uncategorized
        for category, fps in confident_fps.items():
            for i in range(0, len(fps), CHUNK_SIZE):
                chunk = fps[i:i + CHUNK_SIZE]
                client.table("transactions").update(
                    {"category": category, "suggested_category": None, "confidence_score": None}
                ).eq("user_id", user_id).eq("category", "Uncategorized").in_("fingerprint", chunk).execute()
                classified += len(chunk)

        # Update uncertain predictions
        uncertain_groups: dict[tuple[str, float], list[str]] = defaultdict(list)
        for row in uncertain_rows:
            uncertain_groups[(row["suggested"], row["confidence"])].append(row["fp"])

        for (suggested, confidence), fps in uncertain_groups.items():
            for i in range(0, len(fps), CHUNK_SIZE):
                chunk = fps[i:i + CHUNK_SIZE]
                client.table("transactions").update({
                    "category": "Uncategorized",
                    "suggested_category": suggested,
                    "confidence_score": confidence,
                }).eq("user_id", user_id).eq("category", "Uncategorized").in_("fingerprint", chunk).execute()
                classified += len(chunk)

        # Mark import job as complete
        if job_id:
            try:
                client.table("import_jobs").update({
                    "status": "complete",
                    "classified": classified,
                    "completed_at": datetime.utcnow().isoformat(),
                }).eq("id", job_id).execute()
            except Exception:
                pass

        logger.info(
            "bg_classify_complete",
            user_id=user_id,
            confident=sum(len(v) for v in confident_fps.values()),
            uncertain=len(uncertain_rows),
        )
    except Exception as e:
        logger.warning("bg_category_update_failed", user_id=user_id, error=str(e))
        if job_id:
            try:
                from supabase import create_client
                from apps.api.core.auth import _get_supabase_url, _get_supabase_anon_key
                _c = create_client(_get_supabase_url(), _get_supabase_anon_key())
                _c.postgrest.auth(token)
                _c.table("import_jobs").update(
                    {"status": "failed", "error_message": str(e)}
                ).eq("id", job_id).execute()
            except Exception:
                pass


@router.post("/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    password: str = Form(None),
    client: Client = Depends(get_user_client),
):
    """Parse-only endpoint — returns parsed transactions without inserting."""
    allowed_extensions = (".csv", ".tsv", ".xls", ".xlsx", ".xlsm", ".json", ".txt", ".pdf")
    filename = file.filename or ""
    if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Accepted: {', '.join(allowed_extensions)}",
        )

    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="File too large (max 500MB)")

        df = await asyncio.to_thread(parse_file, contents, file.filename, password)

        if "date" in df.columns:
            df = df.dropna(subset=["date"])
            df = df[df["date"].astype(str).str.strip().ne("")]

        df = df.replace([np.nan, np.inf, -np.inf], None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("file_parse_failed", error=str(e), filename=filename)
        raise HTTPException(status_code=400, detail="Failed to parse file")

    transactions = []
    for idx, row in df.iterrows():
        tx = row.to_dict()
        tx["fingerprint"] = generate_fingerprint(
            date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0)),
            merchant=str(tx.get("merchant", "") or ""),
            description=str(tx.get("description", "") or ""),
            payment_method=str(tx.get("method", "") or ""),
            reference=str(tx.get("ref", "") or ""),
        )
        transactions.append(tx)

    logger.info("ingest_complete", count=len(transactions), filename=filename)
    return {"transactions": transactions, "count": len(transactions)}


@router.post("/import")
async def import_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    password: str = Form(None),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    idempotency_key: str | None = Depends(get_idempotency_key),
):
    """v3 Import: insert-first, classify-later.

    1. Parse file
    2. File-hash dedup (reject already-uploaded files)
    3. Build rows + fingerprints
    4. Insert ALL as Uncategorized via single RPC (ON CONFLICT handles dedup)
    5. Enqueue background classification
    6. Return immediately — categories appear via refreshAfterImport()
    """
    async def _execute():
        timings: dict[str, float] = {}
        t_start = time.perf_counter()

        # Rate limit
        limiter = getattr(request.app.state, "import_rate_limiter", None)
        if limiter:
            await limiter(request)

        # Validate file type
        allowed_extensions = (".csv", ".tsv", ".xls", ".xlsx", ".xlsm", ".json", ".txt", ".pdf")
        filename = file.filename or ""
        if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Accepted: {', '.join(allowed_extensions)}",
            )

        # Read file
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)",
            )

        # --- File-hash dedup (instant rejection for re-uploads) ---
        file_hash = hashlib.sha256(contents).hexdigest()
        try:
            existing_file = client.table("uploaded_files").select("id").eq(
                "user_id", user_id
            ).eq("file_hash", file_hash).execute()
            if existing_file.data:
                logger.info("file_already_imported", user_id=user_id, filename=filename)
                return {
                    "inserted": 0,
                    "skipped_duplicates": 0,
                    "total_parsed": 0,
                    "filename": filename,
                    "message": "This file was already imported",
                }
        except Exception as e:
            logger.warning("file_hash_check_failed", error=str(e))

        # --- Stage 1: Parse file ---
        t0 = time.perf_counter()
        try:
            df = await asyncio.to_thread(parse_file, contents, file.filename, password)

            if "date" in df.columns:
                df = df.dropna(subset=["date"])
                df = df[df["date"].astype(str).str.strip().ne("")]
                df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")

            df = df.replace([np.nan, np.inf, -np.inf], None)

        except HTTPException:
            raise
        except Exception as e:
            err_lower = str(e).lower()
            if "password" in err_lower or "encrypted" in err_lower or "decryption" in err_lower:
                raise HTTPException(
                    status_code=400,
                    detail="File is password-protected. Please provide the password.",
                )
            logger.error("import_parse_failed", error=str(e), filename=filename, exc_info=True)
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

        timings["parse_ms"] = round((time.perf_counter() - t0) * 1000)

        if df.empty:
            return {
                "inserted": 0,
                "skipped_duplicates": 0,
                "total_parsed": 0,
                "filename": filename,
            }

        # --- Stage 2: Build rows + fingerprints ---
        t1 = time.perf_counter()
        insert_rows: list[dict] = []
        fps_to_desc: dict[str, str] = {}

        for _, row in df.iterrows():
            tx = row.to_dict()
            fp = generate_fingerprint(
                date=str(tx.get("date", "")),
                amount=float(tx.get("amount", 0) or 0),
                merchant=str(tx.get("merchant", "") or ""),
                description=str(tx.get("description", "") or ""),
                payment_method=str(tx.get("method", "") or ""),
                reference=str(tx.get("ref", "") or ""),
            )

            tx_row = _build_transaction_row(tx, user_id, fp)
            insert_rows.append(tx_row)

            desc = str(tx.get("description", "") or "")
            if desc.strip():
                fps_to_desc[fp] = desc

        timings["build_ms"] = round((time.perf_counter() - t1) * 1000)

        # --- Stage 3: Insert via RPC (ON CONFLICT handles dedup) ---
        # For large files (>PRIORITY_THRESHOLD rows): priority insert — sort by date desc,
        # insert latest 100 rows synchronously so user sees data immediately (~1s),
        # then insert remaining rows in background alongside classification.
        t2 = time.perf_counter()
        total_inserted = 0
        total_skipped = 0

        is_large_file = len(insert_rows) > PRIORITY_THRESHOLD

        if is_large_file:
            # Sort by transaction_date descending to surface newest rows first
            try:
                insert_rows.sort(key=lambda r: r.get("transaction_date", ""), reverse=True)
            except Exception:
                pass

            priority_rows = insert_rows[:100]
            remaining_rows = insert_rows[100:]

            # Synchronous insert: latest 100 rows only
            try:
                for i in range(0, len(priority_rows), MAX_RPC_BATCH):
                    chunk = priority_rows[i:i + MAX_RPC_BATCH]
                    ins, skip = _rpc_insert_batch(client, user_id, chunk)
                    total_inserted += ins
                    total_skipped += skip
            except Exception as e:
                logger.error("priority_insert_failed", error=str(e), exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to insert transactions: {e}")

            timings["priority_insert_ms"] = round((time.perf_counter() - t2) * 1000)
            logger.info(
                "priority_insert_complete",
                priority=len(priority_rows),
                remaining=len(remaining_rows),
                **timings,
            )
        else:
            # Normal file: insert everything synchronously
            remaining_rows = []
            try:
                for i in range(0, len(insert_rows), MAX_RPC_BATCH):
                    chunk = insert_rows[i:i + MAX_RPC_BATCH]
                    ins, skip = _rpc_insert_batch(client, user_id, chunk)
                    total_inserted += ins
                    total_skipped += skip
            except Exception as e:
                logger.error("rpc_insert_failed", error=str(e), exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to insert transactions: {e}")

        timings["insert_ms"] = round((time.perf_counter() - t2) * 1000)
        timings["total_ms"] = round((time.perf_counter() - t_start) * 1000)


        # --- Record uploaded file ---
        try:
            client.table("uploaded_files").insert({
                "user_id": user_id,
                "file_hash": file_hash,
                "filename": filename,
                "upload_type": "import",
            }).execute()
        except Exception as e:
            logger.warning("uploaded_file_tracking_failed", error=str(e))

        # --- Create import job for monitoring ---
        job_id: str | None = None
        try:
            job_res = client.table("import_jobs").insert({
                "user_id": user_id,
                "status": "classifying",
                "filename": filename,
                "total_parsed": len(insert_rows),
                "inserted": total_inserted,
                "skipped_duplicates": total_skipped,
                "timings": timings,
            }).execute()
            if job_res.data:
                job_id = job_res.data[0].get("id")
        except Exception as e:
            logger.warning("import_job_tracking_failed", error=str(e))

        # --- Enqueue background tasks ---
        token = request.headers.get("Authorization", "")[7:].strip()

        # For large files: insert remaining rows in background first
        if is_large_file and remaining_rows:
            background_tasks.add_task(
                _insert_remaining_rows, user_id, remaining_rows, token, job_id
            )

        # Classify and update categories in background
        if fps_to_desc:
            background_tasks.add_task(
                _classify_and_update_transactions, user_id, fps_to_desc, token, job_id
            )

        logger.info(
            "import_complete",
            inserted=total_inserted,
            skipped_duplicates=total_skipped,
            total=len(insert_rows),
            filename=filename,
            **timings,
        )

        return {
            "inserted": total_inserted,
            "skipped_duplicates": total_skipped,
            "total_parsed": len(insert_rows),
            "filename": filename,
        }
    return await with_idempotency(idempotency_key, _execute)
