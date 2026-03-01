"""Ingestion router — CSV upload and transaction import endpoints.

Absorbs the CSV ingest logic from the old routers/ingestion.py.
Uses the new unified generate_fingerprint (BUG-02 fix).

Frontend Migration: Added POST /import for full end-to-end import
(parse + classify + insert). The frontend no longer does any parsing.
"""

import hashlib
import structlog
import numpy as np
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from supabase import Client

from apps.api.core.auth import get_user_client
from packages.ingestion_engine.import_transactions import parse_file
from apps.api.domains.ingestion.service import generate_fingerprint

router = APIRouter(prefix="/ingest", tags=["ingestion"])
logger = structlog.get_logger()

MAX_UPLOAD_BYTES = 500 * 1024 * 1024  # 500 MB (large bank statements)
BATCH_UPSERT_SIZE = 500


def _classify_descriptions(descriptions: list[str]) -> dict[str, str]:
    """Classify transaction descriptions using HypCD, with keyword fallback.

    Returns a dict mapping description -> category.
    """
    result: dict[str, str] = {}
    if not descriptions:
        return result

    # Try HypCD classifier first
    try:
        from apps.api.domains.categorization.service import classify_batch_in_process

        classifications = classify_batch_in_process(descriptions)
        for desc, clf in zip(descriptions, classifications):
            result[desc] = clf.get("category", "Uncategorized")
        return result
    except Exception as e:
        logger.warning("hypcd_unavailable_for_import", error=str(e))

    # Fallback: keyword-based classification
    keyword_map = [
        ("Food", ["swiggy", "zomato", "food", "restaurant", "dining", "blinkit",
                   "zepto", "bigbasket", "mcdonalds", "kfc", "burger", "pizza",
                   "dominos", "subway", "starbucks", "cafe", "bakery"]),
        ("Grocery", ["grocery", "grofers", "dmart", "supermarket", "provision"]),
        ("Shopping", ["amazon", "flipkart", "myntra", "ajio", "shop", "mall",
                      "cloth", "fashion", "meesho", "nykaa"]),
        ("Transport", ["uber", "ola", "rapido", "taxi", "cab", "auto", "metro",
                       "bus", "train", "fuel", "petrol", "diesel", "parking"]),
        ("Utilities", ["electric", "water", "gas", "bill", "recharge", "airtel",
                       "jio", "vodafone", "broadband", "wifi", "internet"]),
        ("Subscriptions", ["netflix", "spotify", "hotstar", "prime", "youtube",
                          "subscription", "membership"]),
        ("Healthcare", ["hospital", "medical", "pharmacy", "doctor", "medicine",
                       "health", "clinic", "lab", "dental"]),
        ("Education", ["course", "tuition", "school", "college", "udemy",
                      "coursera", "education", "book"]),
        ("Entertainment", ["movie", "cinema", "game", "concert", "ticket",
                          "amusement", "theme park"]),
        ("Finance", ["investment", "loan", "insurance", "mutual fund", "zerodha",
                    "groww", "emi", "sip", "bank charge"]),
        ("Income", ["salary", "refund", "cashback", "dividend", "interest earned"]),
        ("People", ["sent to", "received from", "upi transfer", "transfer to"]),
    ]

    for desc in descriptions:
        desc_lower = desc.lower()
        matched = "Uncategorized"
        for category, keywords in keyword_map:
            if any(kw in desc_lower for kw in keywords):
                matched = category
                break
        result[desc] = matched

    return result


def _classify_and_update_transactions(user_id: str, fps_to_desc: dict, token: str) -> None:
    """Background task: classify inserted transactions and patch their categories.

    Runs after the HTTP response is sent so /import responds in milliseconds.
    Uses the user's JWT (passed from the request) so no SUPABASE_SERVICE_KEY
    is required — RLS still enforces user isolation.
    """
    unique_descs = list({desc for desc in fps_to_desc.values() if desc.strip()})
    if not unique_descs:
        return

    try:
        category_map = _classify_descriptions(unique_descs)
    except Exception as e:
        logger.warning("bg_classify_failed", error=str(e))
        return

    # Group fingerprints by resolved category for batch updates
    category_to_fps: dict = defaultdict(list)
    for fp, desc in fps_to_desc.items():
        category = category_map.get(desc, "Uncategorized")
        if category != "Uncategorized":
            category_to_fps[category].append(fp)

    if not category_to_fps:
        return

    try:
        from supabase import create_client
        from apps.api.core.auth import _get_supabase_url, _get_supabase_anon_key
        client = create_client(_get_supabase_url(), _get_supabase_anon_key())
        client.auth.set_session(token, "")
        for category, fps in category_to_fps.items():
            client.table("transactions").update(
                {"category": category}
            ).eq("user_id", user_id).in_("fingerprint", fps).execute()
        logger.info(
            "bg_classify_complete",
            user_id=user_id,
            categories=len(category_to_fps),
            total=len(fps_to_desc),
        )
    except Exception as e:
        logger.warning("bg_category_update_failed", user_id=user_id, error=str(e))


def _run_contrastive_pretraining_bg(
    user_id: str,
    descriptions: list[str],
    token: str,
) -> None:
    """Background task: unsupervised contrastive pretraining on imported transactions.

    Runs after /import completes. No labels required — uses augmented positive pairs.
    Updates the per-user adapter (projector weights) and persists to Supabase Storage.
    """
    if len(descriptions) < 4:
        return

    try:
        from apps.api.domains.categorization.service import get_classifier
        from packages.categorization.adapter_manager import AdapterManager

        classifier = get_classifier()
        mgr = AdapterManager()

        user_state = mgr.load_user_adapter(user_id)
        if user_state:
            try:
                classifier.load_state_dict(user_state)
            except Exception:
                pass

        mgr.run_contrastive_pretraining(classifier, descriptions, epochs=3)
        mgr.save_user_adapter(user_id, classifier.state_dict())

        logger.info(
            "contrastive_pretraining_complete",
            user_id=user_id,
            descriptions=len(descriptions),
        )
    except Exception as e:
        logger.warning("contrastive_pretraining_failed", user_id=user_id, error=str(e))


def _build_transaction_row(
    row: dict,
    user_id: str,
    fingerprint: str,
    category: str = "Uncategorized",
) -> dict:
    """Build a Supabase-ready transaction row from a parsed row."""
    amount = float(row.get("amount", 0) or 0)

    # Determine type from amount
    tx_type = "credit" if amount >= 0 else "debit"

    return {
        "user_id": user_id,
        "transaction_date": str(row.get("date", "")),
        "amount": amount,
        "currency": str(row.get("currency", "INR") or "INR"),
        "description": str(row.get("description", "") or ""),
        "merchant_name": str(row.get("merchant", "") or ""),
        "category": category,
        "payment_method": str(row.get("payment_method", "") or ""),
        "status": str(row.get("status", "completed") or "completed"),
        "type": tx_type,
        "fingerprint": fingerprint,
        "raw_data": {k: v for k, v in row.items() if v is not None},
    }


@router.post("/csv")
async def ingest_csv(
    file: UploadFile = File(...),
    password: str = Form(None),
    client: Client = Depends(get_user_client),
):
    """Accept a CSV or Excel file, parse and fingerprint transactions.

    Parse-only endpoint — returns parsed transactions without inserting.
    Useful for previewing data before committing an import.
    """
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
    client: Client = Depends(get_user_client),
):
    """Full end-to-end import: parse file → classify → deduplicate → insert.

    This is the main import endpoint used by the frontend. It:
    1. Parses the uploaded file (CSV, Excel, JSON, etc.)
    2. Generates unified fingerprints for deduplication
    3. Classifies transactions via HypCD (keyword fallback)
    4. Checks for duplicate fingerprints in the database
    5. Inserts new transactions in batches

    Returns counts of inserted, skipped (duplicate), and total parsed rows.
    """
    # Apply rate limit if limiter is configured on app state (10 req/min per user)
    limiter = getattr(request.app.state, "import_rate_limiter", None)
    if limiter:
        await limiter(request)

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

    user_id = user_response.user.id

    # --- Step 1: Parse file ---
    try:
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)}MB)",
            )

        df = parse_file(contents, file.filename, password=password)

        if "date" in df.columns:
            df = df.dropna(subset=["date"])
            df = df[df["date"].astype(str).str.strip().ne("")]

        df = df.replace([np.nan, np.inf, -np.inf], None)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("import_parse_failed", error=str(e), filename=filename)
        if "password" in str(e).lower() or "encrypted" in str(e).lower():
            raise HTTPException(
                status_code=400,
                detail="File is password-protected. Please provide the password.",
            )
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    if df.empty:
        return {
            "inserted": 0,
            "skipped_duplicates": 0,
            "cancelled": 0,
            "total_parsed": 0,
            "filename": filename,
        }

    # --- Track uploaded file ---
    file_hash = hashlib.sha256(contents).hexdigest()
    try:
        client.table("uploaded_files").insert({
            "user_id": user_id,
            "file_hash": file_hash,
            "filename": filename,
            "upload_type": "training",
        }).execute()
    except Exception as e:
        logger.warning("uploaded_file_tracking_failed", error=str(e))

    # --- Step 2: Fingerprint all rows ---
    parsed_rows = []
    fingerprints = []
    for idx, row in df.iterrows():
        tx = row.to_dict()
        fp = generate_fingerprint(
            date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0) or 0),
            merchant=str(tx.get("merchant", "") or ""),
            description=str(tx.get("description", "") or ""),
            payment_method=str(tx.get("method", "") or ""),
            reference=str(tx.get("ref", "") or ""),
        )
        parsed_rows.append(tx)
        fingerprints.append(fp)

    # --- Step 3: Deduplicate against database (paginated to bypass 1000-row limit) ---
    existing_fps: set = set()
    try:
        page_size = 1000
        offset = 0
        while True:
            existing_result = (
                client.table("transactions")
                .select("fingerprint")
                .eq("user_id", user_id)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            page = existing_result.data or []
            for row in page:
                if row.get("fingerprint"):
                    existing_fps.add(row["fingerprint"])
            if len(page) < page_size:
                break
            offset += page_size
    except Exception as e:
        logger.warning("fingerprint_lookup_failed", error=str(e))
        existing_fps = set()

    # Filter out duplicates and build unique rows
    new_rows = []
    seen_fps = set()
    skipped = 0
    for row, fp in zip(parsed_rows, fingerprints):
        if fp in existing_fps or fp in seen_fps:
            skipped += 1
            continue
        seen_fps.add(fp)
        new_rows.append((row, fp))

    if not new_rows:
        return {
            "inserted": 0,
            "skipped_duplicates": skipped,
            "total_parsed": len(parsed_rows),
            "filename": filename,
        }

    # --- Step 4: Collect unique descriptions for async classification ---
    unique_descs = list({
        str(row.get("description", "") or "")
        for row, _ in new_rows
        if str(row.get("description", "") or "").strip()
    })

    # --- Track classification job (async — categories patched after response) ---
    try:
        client.table("classification_jobs").insert({
            "user_id": user_id,
            "status": "pending",
            "logs": f"Queued async classification for {len(unique_descs)} descriptions from {filename}",
        }).execute()
    except Exception as e:
        logger.warning("classification_job_tracking_failed", error=str(e))

    # --- Step 5: Build insert rows (Uncategorized — classification is async) ---
    insert_rows = []
    fps_to_desc: dict = {}
    cancelled_count = 0
    for row, fp in new_rows:
        desc = str(row.get("description", "") or "")
        fps_to_desc[fp] = desc
        tx_row = _build_transaction_row(row, user_id, fp)  # defaults to "Uncategorized"

        # Track cancelled transactions (amount=0, no money moved)
        if tx_row["amount"] == 0 or tx_row["amount"] == 0.0:
            tx_row["status"] = "cancelled"
            cancelled_count += 1

        insert_rows.append(tx_row)

    # --- Step 6: Batch insert ---
    inserted = 0
    for i in range(0, len(insert_rows), BATCH_UPSERT_SIZE):
        batch = insert_rows[i : i + BATCH_UPSERT_SIZE]
        try:
            result = client.table("transactions").insert(batch).execute()
            inserted += len(result.data) if result.data else len(batch)
        except Exception as e:
            logger.error(
                "batch_insert_failed",
                error=str(e),
                batch_start=i,
                batch_size=len(batch),
            )
            # Try inserting one by one for this batch to salvage what we can
            for row in batch:
                try:
                    client.table("transactions").insert(row).execute()
                    inserted += 1
                except Exception:
                    skipped += 1

    # --- Enqueue background classification (patches categories after response) ---
    # Extract the JWT from the Authorization header so the background task can
    # create a user-scoped Supabase client without needing SUPABASE_SERVICE_KEY.
    if fps_to_desc:
        token = request.headers.get("Authorization", "")[7:].strip()
        background_tasks.add_task(_classify_and_update_transactions, user_id, fps_to_desc, token)

        # Enqueue contrastive pretraining (updates projector weights from unlabeled data)
        unique_descs = list({desc for desc in fps_to_desc.values() if desc.strip()})
        if unique_descs:
            background_tasks.add_task(
                _run_contrastive_pretraining_bg, user_id, unique_descs, token
            )

    logger.info(
        "import_complete",
        inserted=inserted,
        skipped_duplicates=skipped,
        cancelled=cancelled_count,
        total=len(parsed_rows),
        filename=filename,
    )

    return {
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "cancelled": cancelled_count,
        "total_parsed": len(parsed_rows),
        "filename": filename,
    }
