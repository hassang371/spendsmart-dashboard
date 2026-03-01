# Fix All Code Review Issues Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Systematically fix all 20 issues (5 Critical, 9 Important, 6 Suggestions) identified in the full codebase review.

**Architecture:** Fix issues in priority order: Critical → Important → Suggestions. Backend fixes first, then frontend. Each fix is self-contained with its own test verification.

**Tech Stack:** FastAPI (Python 3.14), Next.js 16 (TypeScript), Supabase, Redis, Celery

---

## BATCH 1 — Critical Backend Fixes

---

### Task 1: CRIT-01 — Fix Fingerprint Mismatch in Ingestion Router

**Problem:** `apps/api/domains/ingestion/router.py` imports `generate_fingerprint` from `packages/ingestion_engine/import_transactions.py` (3-field) instead of `apps/api/domains/ingestion/service.py` (6-field canonical). Deduplication is broken between `/ingest/import` and `/training/upload`.

**Files:**
- Modify: `apps/api/domains/ingestion/router.py` (line 17, lines 157-162, lines 254-261)

**Step 1: Update the import**

In `apps/api/domains/ingestion/router.py`, change line 17 from:
```python
from packages.ingestion_engine.import_transactions import parse_file, generate_fingerprint
```
to:
```python
from packages.ingestion_engine.import_transactions import parse_file
from apps.api.domains.ingestion.service import generate_fingerprint
```

**Step 2: Fix fingerprint call in `/csv` endpoint (lines 157-162)**

Change:
```python
        tx["fingerprint"] = generate_fingerprint(
            date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0)),
            merchant=str(tx.get("merchant", "")),
            salt=f"row_{idx}",
        )
```
to:
```python
        tx["fingerprint"] = generate_fingerprint(
            date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0)),
            merchant=str(tx.get("merchant", "") or ""),
            description=str(tx.get("description", "") or ""),
            payment_method=str(tx.get("method", "") or ""),
            reference=str(tx.get("ref", "") or ""),
        )
```

**Step 3: Fix fingerprint call in `/import` endpoint (lines 254-261)**

Change:
```python
        fp = generate_fingerprint(
            date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0) or 0),
            merchant=str(tx.get("merchant", "") or ""),
            salt=f"row_{idx}",
        )
```
to:
```python
        fp = generate_fingerprint(
            date=str(tx.get("date", "")),
            amount=float(tx.get("amount", 0) or 0),
            merchant=str(tx.get("merchant", "") or ""),
            description=str(tx.get("description", "") or ""),
            payment_method=str(tx.get("method", "") or ""),
            reference=str(tx.get("ref", "") or ""),
        )
```

**Step 4: Run tests**

```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP"
source .venv/bin/activate
python -m pytest apps/api/domains/ingestion/tests/ -v --tb=short
```
Expected: All ingestion tests pass.

**Step 5: Commit**
```bash
git add apps/api/domains/ingestion/router.py
git commit -m "fix(ingestion): use canonical 6-field fingerprint in /csv and /import endpoints

CRIT-01: Both /ingest/csv and /ingest/import now use the same
generate_fingerprint from ingestion/service.py (6 fields) as
/training/upload, fixing broken deduplication across import paths."
```

---

### Task 2: CRIT-02 — Fix Route Ordering in Accounts Router

**Problem:** `PATCH /accounts/transactions/{transaction_id}` is registered before `PATCH /accounts/transactions/batch`. FastAPI matches in registration order, so `"batch"` is captured as `transaction_id` and the batch endpoint is unreachable.

**Files:**
- Modify: `apps/api/domains/accounts/router.py` (lines 92 and 141)

**Step 1: Move the batch route before the dynamic route**

In `apps/api/domains/accounts/router.py`, swap the order of the two PATCH endpoints so `@router.patch("/transactions/batch")` comes BEFORE `@router.patch("/transactions/{transaction_id}")`.

The file currently has them in this order:
- Line 92: `@router.patch("/transactions/{transaction_id}")`
- Line 141: `@router.patch("/transactions/batch")`

Move the entire `batch_update_transactions` function (lines 141-183) to appear BEFORE the `update_transaction` function (lines 92-138).

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/accounts/tests/ -v --tb=short
```
Expected: All accounts tests pass.

**Step 3: Verify route ordering manually (quick sanity check)**
```bash
python -c "
from apps.api.domains.accounts.router import router
routes = [(r.path, list(r.methods)) for r in router.routes]
print(routes)
"
```
Expected: `/transactions/batch` appears before `/transactions/{transaction_id}` in the output.

**Step 4: Commit**
```bash
git add apps/api/domains/accounts/router.py
git commit -m "fix(accounts): register /transactions/batch before /{transaction_id}

CRIT-02: Static route must precede dynamic route in FastAPI registration
order. Previously /batch was unreachable as 'batch' was matched as
transaction_id parameter."
```

---

### Task 3: CRIT-03 — Fix Deduplication Fingerprint Fetch (Supabase 1000-Row Limit)

**Problem:** The `/ingest/import` endpoint fetches ALL user fingerprints with a single `.execute()` call, which Supabase caps at 1,000 rows. Users with >1,000 transactions get silent data duplication on every import.

**Files:**
- Modify: `apps/api/domains/ingestion/router.py` (lines 263-279)

**Step 1: Replace single-query fetch with paginated fetch using `range()`**

Replace the existing fingerprint fetch block (lines 263-279) with:

```python
    # --- Step 3: Deduplicate against database (paginated to bypass 1000-row limit) ---
    existing_fps: set[str] = set()
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
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/ingestion/tests/ -v --tb=short
```
Expected: All ingestion tests pass.

**Step 3: Commit**
```bash
git add apps/api/domains/ingestion/router.py
git commit -m "fix(ingestion): paginate fingerprint dedup fetch to bypass 1000-row limit

CRIT-03: Supabase Python client defaults to max 1000 rows. Users with
>1000 transactions had silent deduplication failures causing re-insertion
of already-imported transactions. Now paginates through all pages."
```

---

### Task 4: CRIT-04 — Add Ownership Check to Training Status Endpoint

**Problem:** `GET /training/status/{job_id}` fetches a job by ID only, with no check that the authenticated user owns that job. Any authenticated user can read any job's data (IDOR).

**Files:**
- Modify: `apps/api/domains/training/router.py` (lines 169-186)

**Step 1: Add user_id filter to the status query**

Replace the `get_training_status` function body:
```python
@router.get("/status/{job_id}")
async def get_training_status(
    job_id: str,
    client: Client = Depends(get_user_client),
):
    """Get training job status by ID."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id

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
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/training/ -v --tb=short
```
Expected: All training tests pass.

**Step 3: Commit**
```bash
git add apps/api/domains/training/router.py
git commit -m "fix(training): add user ownership check to GET /training/status/{job_id}

CRIT-04: IDOR vulnerability — any authenticated user could read any
training job by guessing its UUID. Now filters by both job_id and
user_id. Returns 404 if job not found or not owned by caller."
```

---

### Task 5: CRIT-05 — Fix ContentSizeLimit Constant and Comment

**Problem:** `main.py` has a misleading comment ("Reject bodies > 10 MB") while the actual limit is 500 MB. The constant and comment are inconsistent. CLAUDE.md documents it as 10 MB.

The 500 MB limit is intentional for large bank statement files. The fix is to make the constant, comment, and documentation consistent.

**Files:**
- Modify: `apps/api/main.py` (lines 49, 55-57, 192)

**Step 1: Fix the comment on the middleware registration (line 192)**

Change:
```python
# M3: Reject bodies > 10 MB before they hit domain logic
app.add_middleware(ContentSizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)
```
to:
```python
# M3: Reject bodies > 500 MB before they hit domain logic (large bank statement files)
app.add_middleware(ContentSizeLimitMiddleware, max_bytes=MAX_REQUEST_BODY_BYTES)
```

**Step 2: Fix the docstring of ContentSizeLimitMiddleware (lines 55-57)**

Change:
```python
    """Reject requests with Content-Length exceeding the configured limit.

    Prevents DoS via oversized payloads. Uploads capped at 500 MB
    to support large bank statement files (250k+ rows).
    """
```
(This is already correct — no change needed here.)

**Step 3: Update CLAUDE.md security hardening note**

In `CLAUDE.md`, change:
```
- **Payload Limits:** Strict 10MB limit via `ContentSizeLimitMiddleware` preventing DoS payloads.
```
to:
```
- **Payload Limits:** 500MB limit via `ContentSizeLimitMiddleware` (supports large bank statement files). Note: middleware only checks `Content-Length` header; chunked uploads bypass this check and are bounded by the router's `MAX_UPLOAD_BYTES` check instead.
```

**Step 4: Run tests**
```bash
python -m pytest apps/api/ -v --tb=short -q
```
Expected: All tests pass.

**Step 5: Commit**
```bash
git add apps/api/main.py CLAUDE.md
git commit -m "fix(main): correct ContentSizeLimitMiddleware comment from 10MB to 500MB

CRIT-05: Comment said 10MB, actual limit was 500MB. Fixed comment and
updated CLAUDE.md to reflect actual behaviour and chunked-upload caveat."
```

---

## BATCH 2 — Important Backend Fixes

---

### Task 6: IMP-01 — Add Clock Skew Tolerance to JWT Expiry Check

**Problem:** JWT `exp` check in `auth.py` uses exact `time.time()` with no tolerance. Tokens expiring in the next 1-2 seconds get 401 from the pre-flight check while Supabase would still accept them.

**Files:**
- Modify: `apps/api/core/auth.py` (lines 99-105)

**Step 1: Add 30-second skew buffer**

Change:
```python
        exp = payload.get("exp")
        if exp is not None and time.time() > exp:
            logger.warning("jwt_expired", exp=exp)
            raise HTTPException(
                status_code=401,
                detail="Token has expired. Please sign in again.",
            )
```
to:
```python
        exp = payload.get("exp")
        CLOCK_SKEW_SECONDS = 30
        if exp is not None and time.time() > (exp + CLOCK_SKEW_SECONDS):
            logger.warning("jwt_expired", exp=exp)
            raise HTTPException(
                status_code=401,
                detail="Token has expired. Please sign in again.",
            )
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/core/ -v --tb=short
```
Expected: All core tests pass.

**Step 3: Commit**
```bash
git add apps/api/core/auth.py
git commit -m "fix(auth): add 30s clock skew tolerance to JWT expiry pre-flight check

IMP-01: Tokens expiring in the next 30 seconds are accepted by the
pre-flight check (Supabase performs definitive validation downstream)."
```

---

### Task 7: IMP-03 — Wire Rate Limiter to the Import Endpoint

**Problem:** `RateLimiter` and `rate_limit_dependency` are built but never applied to any endpoint. The expensive `/ingest/import` endpoint (ML inference + DB writes) is completely unprotected.

**Files:**
- Modify: `apps/api/main.py` (add Redis client init)
- Modify: `apps/api/domains/ingestion/router.py` (apply rate limit to `/import`)

**Step 1: Initialize Redis client and rate limiter in main.py**

After the existing imports in `main.py`, add:
```python
from apps.api.core.rate_limiter import RateLimiter, rate_limit_dependency
```

In the `lifespan` function, after `setup_logging(...)`, add:
```python
    # Initialize Redis-backed rate limiter for import endpoint
    import redis as _redis
    try:
        _redis_client = _redis.from_url(
            os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=True,
            socket_connect_timeout=2,
        )
        _redis_client.ping()
        app.state.import_rate_limiter = rate_limit_dependency(
            RateLimiter(_redis_client, max_requests=10, window_seconds=60)
        )
        logger.info("rate_limiter_initialized")
    except Exception as e:
        logger.warning("rate_limiter_unavailable", error=str(e))
        app.state.import_rate_limiter = None
```

**Step 2: Apply rate limiter to `/import` endpoint in ingestion router**

In `apps/api/domains/ingestion/router.py`, update the `/import` endpoint signature to use a request-scoped dependency:

```python
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

@router.post("/import")
async def import_file(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(None),
    client: Client = Depends(get_user_client),
):
    # Apply rate limit if limiter is configured
    limiter = getattr(request.app.state, "import_rate_limiter", None)
    if limiter:
        await limiter(request)
    # ... rest of function unchanged
```

**Step 3: Run tests**
```bash
python -m pytest apps/api/ -v --tb=short -q
```
Expected: All tests pass (rate limiter fails open if Redis unavailable in test env).

**Step 4: Commit**
```bash
git add apps/api/main.py apps/api/domains/ingestion/router.py
git commit -m "fix(rate-limit): wire Redis rate limiter to /ingest/import endpoint

IMP-03: Rate limiter existed but was never applied. /ingest/import now
enforces 10 requests/minute per user. Fails open if Redis unavailable."
```

---

### Task 8: IMP-05 — Move Duplicate-File Check Before Parse in forecast/predict

**Problem:** `/forecast/predict` runs full parse + ML pipeline before checking if the file was already uploaded. Should hash-check first, then parse.

**Files:**
- Modify: `apps/api/domains/forecasting/router.py` (lines 26-105)

**Step 1: Restructure endpoint — auth + duplicate check first, then parse**

Replace the entire `forecast_predict` function with:
```python
@router.post("/predict")
async def forecast_predict(
    file: UploadFile = File(...),
    client: Client = Depends(get_user_client),
):
    """Accept a CSV of transactions and return predicted spending."""
    if (
        file.content_type
        and "csv" not in file.content_type
        and "text" not in file.content_type
    ):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    # Auth check first
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    user_id = user_response.user.id

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    # Duplicate-file check BEFORE parsing (fail fast)
    try:
        client.table("uploaded_files").insert({
            "user_id": user_id,
            "file_hash": file_hash,
            "filename": file.filename,
            "upload_type": "forecast",
        }).execute()
    except Exception as e:
        if "duplicate key" in str(e) or "23505" in str(e):
            raise HTTPException(
                status_code=400,
                detail="This file has already been uploaded for forecasting.",
            )
        raise HTTPException(status_code=500, detail="Failed to register upload")

    # Parse only after successful registration
    try:
        df = parse_file(contents, file.filename)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse CSV")

    if "transaction_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"transaction_date": "date"})

    try:
        loader = TransactionLoader(df)
        daily_df = loader.aggregate_daily()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to aggregate transactions")

    # Statistical forecast
    horizon = 7
    recent = daily_df.tail(min(30, len(daily_df)))
    avg_daily_spend = (
        float(recent["daily_spend"].mean()) if "daily_spend" in recent.columns else 0.0
    )
    avg_daily_income = (
        float(recent["daily_income"].mean()) if "daily_income" in recent.columns else 0.0
    )

    predictions = [
        {
            "day_offset": day,
            "predicted_spend": round(avg_daily_spend, 2),
            "predicted_income": round(avg_daily_income, 2),
            "predicted_net": round(avg_daily_income - avg_daily_spend, 2),
        }
        for day in range(1, horizon + 1)
    ]

    return {
        "predictions": predictions,
        "horizon_days": horizon,
        "model": "statistical_mvp",
        "note": "Using rolling average. TFT model used when trained checkpoint available.",
    }
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/forecasting/ -v --tb=short
```
Expected: All forecasting tests pass.

**Step 3: Commit**
```bash
git add apps/api/domains/forecasting/router.py
git commit -m "fix(forecasting): check duplicate file before parsing in /forecast/predict

IMP-05: Auth and file hash check now happen before expensive parse+ML
pipeline. Duplicate uploads fail fast instead of after full processing."
```

---

### Task 9: IMP-06 — Fix Cursor Pagination to Use Composite Key

**Problem:** `accounts/service.py` decodes `cursor_id` from the cursor but never uses it. When two transactions share the same `created_at` timestamp, cursor position is ambiguous — rows are skipped or duplicated across pages.

**Files:**
- Modify: `apps/api/domains/accounts/service.py` (lines 44-49)

**Step 1: Use composite (created_at, id) filter for proper keyset pagination**

Replace the cursor application block:
```python
    # Apply cursor position if provided
    if pagination.cursor:
        cursor_date, cursor_id = decode_cursor(pagination.cursor)
        # Keyset pagination: fetch rows "before" the cursor
        # Using composite (created_at, id) ordering
        query = query.lt("created_at", cursor_date)
```
with:
```python
    # Apply cursor position if provided
    # True keyset pagination: (created_at < cursor_date) OR
    # (created_at = cursor_date AND id < cursor_id)
    # Supabase Python client doesn't support OR directly in .filter(),
    # so we use the PostgREST "or" filter syntax.
    if pagination.cursor:
        cursor_date, cursor_id = decode_cursor(pagination.cursor)
        query = query.or_(
            f"created_at.lt.{cursor_date},"
            f"and(created_at.eq.{cursor_date},id.lt.{cursor_id})"
        )
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/accounts/tests/ -v --tb=short
```
Expected: All accounts tests pass.

**Step 3: Commit**
```bash
git add apps/api/domains/accounts/service.py
git commit -m "fix(accounts): use composite (created_at, id) keyset for cursor pagination

IMP-06: Previous cursor only filtered on created_at, ignoring cursor_id.
Batch-imported transactions with identical timestamps caused items to be
skipped or duplicated across pages. Now uses proper composite key via
PostgREST OR filter."
```

---

### Task 10: IMP-07 — Update Training Job Status During Retries

**Problem:** Celery task never writes "retrying" status to DB during retry attempts. Job stays at "running" for up to 180 seconds with no user visibility.

**Files:**
- Modify: `apps/api/tasks/training_tasks.py` (lines 111-128)

**Step 1: Add retry status update**

Replace the exception handler block:
```python
    except Exception as exc:
        logger.error(f"Training job {job_id} failed: {exc}")

        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
            # BUG-01 fix: Update DB with failed status
            _update_job_status(
                job_id,
                status="failed",
                error=str(exc),
            )
            return {
                "status": "failed",
                "job_id": job_id,
                "user_id": user_id,
                "error": str(exc),
            }
```
with:
```python
    except Exception as exc:
        logger.error(f"Training job {job_id} failed: {exc}")

        retry_count = self.request.retries
        max_retries = self.max_retries

        if retry_count < max_retries:
            # Update DB to show retry attempt before re-queuing
            _update_job_status(
                job_id,
                status="running",
                error=f"Attempt {retry_count + 1}/{max_retries + 1} failed: {exc}. Retrying...",
            )

        try:
            self.retry(exc=exc)
        except MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for job {job_id}")
            _update_job_status(
                job_id,
                status="failed",
                error=str(exc),
            )
            return {
                "status": "failed",
                "job_id": job_id,
                "user_id": user_id,
                "error": str(exc),
            }
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/tasks/ -v --tb=short 2>/dev/null || echo "No task tests yet — manual verification only"
```

**Step 3: Commit**
```bash
git add apps/api/tasks/training_tasks.py
git commit -m "fix(training): write retry attempt info to DB during Celery retries

IMP-07: Training job was stuck at 'running' with no user feedback during
retry backoff periods. Now updates logs field with attempt count/error
before each retry so users see progress in TrainingJobCard."
```

---

### Task 11: IMP-08 — Update schema.sql with Missing Tables and Indexes

**Problem:** `architecture/schema.sql` is missing: `uploaded_files`, `training_jobs`, `classification_jobs` tables; `fingerprint` and `type` columns on transactions; unique constraint on `(user_id, fingerprint)`; index on `(user_id, created_at)`.

**Files:**
- Modify: `architecture/schema.sql`

**Step 1: Add missing columns to transactions table**

After the `raw_data JSONB,` line, add:
```sql
    fingerprint TEXT,
    type TEXT DEFAULT 'debit',
    original_category TEXT,
```

**Step 2: Add missing indexes**

After the existing index lines, add:
```sql
-- Pagination index (cursor-based pagination orders by user_id, created_at)
CREATE INDEX IF NOT EXISTS idx_transactions_user_created ON transactions(user_id, created_at DESC);

-- Fingerprint deduplication (used in upsert and import dedup checks)
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_fingerprint ON transactions(user_id, fingerprint)
    WHERE fingerprint IS NOT NULL;
```

**Step 3: Add missing tables**

Append to the end of `schema.sql`:
```sql
-- 4. Uploaded Files Table (deduplication by file hash)
CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    file_hash TEXT NOT NULL,
    filename TEXT,
    upload_type TEXT DEFAULT 'import',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, file_hash)
);

ALTER TABLE uploaded_files ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own uploaded files"
ON uploaded_files FOR ALL
USING (auth.uid() = user_id);

-- 5. Training Jobs Table
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    celery_task_id TEXT,
    logs TEXT,
    metrics JSONB,
    checkpoint_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own training jobs"
ON training_jobs FOR SELECT
USING (auth.uid() = user_id);
CREATE POLICY "Service role can manage training jobs"
ON training_jobs FOR ALL
USING (true);

-- 6. Classification Jobs Table
CREATE TABLE IF NOT EXISTS classification_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    logs TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE classification_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own classification jobs"
ON classification_jobs FOR SELECT
USING (auth.uid() = user_id);
```

**Step 4: Commit**
```bash
git add architecture/schema.sql
git commit -m "fix(schema): add missing tables, columns, and indexes

IMP-08: schema.sql was missing uploaded_files, training_jobs,
classification_jobs tables; fingerprint/type columns on transactions;
unique constraint on (user_id, fingerprint); pagination index on
(user_id, created_at DESC)."
```

---

### Task 12: SUG-07 — Remove Filesystem Path from list_models Response

**Problem:** `categorization/router.py` returns the full server filesystem path in the `list_models` API response, leaking container directory structure.

**Files:**
- Modify: `apps/api/domains/categorization/router.py` (lines 207-212)

**Step 1: Remove the `path` field from the model dict**

Change:
```python
            models.append({
                "name": filename,
                "path": filepath,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": stat.st_mtime,
            })
```
to:
```python
            models.append({
                "name": filename,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": stat.st_mtime,
            })
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/categorization/tests/ -v --tb=short
```

**Step 3: Commit**
```bash
git add apps/api/domains/categorization/router.py
git commit -m "fix(categorization): remove server filesystem path from list_models response

SUG-07: Full container path was returned in API response, leaking
directory structure. Replaced with just name/size/created_at."
```

---

## BATCH 3 — Frontend Fixes

---

### Task 13: IMP-02 — Add Max-Page Guard to Pagination Loops

**Problem:** Both `dashboard/page.tsx` and `analytics/page.tsx` have unbounded `while (hasMore)` loops with no maximum page count. If `has_more: true` with `null` next_cursor (a bug condition), the tab hangs forever.

**Files:**
- Modify: `apps/web/app/dashboard/page.tsx` (lines 93-104)
- Modify: `apps/web/app/dashboard/analytics/page.tsx` (lines 62-72)

**Step 1: Add MAX_PAGES guard in dashboard/page.tsx**

Replace:
```typescript
        const allItems: Transaction[] = [];
        let cursor: string | undefined;
        let hasMore = true;

        // Paginate to get all transactions (overview needs all for calculations)
        while (hasMore) {
          const response = await accountsApi.getTransactions(session.access_token, {
            limit: 100,
            cursor,
          });
          allItems.push(...response.items);
          hasMore = response.has_more;
          cursor = response.next_cursor ?? undefined;
        }
```
with:
```typescript
        const allItems: Transaction[] = [];
        let cursor: string | undefined;
        let hasMore = true;
        const MAX_PAGES = 50; // Guard: max 5,000 transactions fetched
        let pagesFetched = 0;

        // Paginate to get all transactions (overview needs all for calculations)
        while (hasMore && pagesFetched < MAX_PAGES) {
          const response = await accountsApi.getTransactions(session.access_token, {
            limit: 100,
            cursor,
          });
          allItems.push(...response.items);
          hasMore = response.has_more && !!response.next_cursor;
          cursor = response.next_cursor ?? undefined;
          pagesFetched++;
        }
```

**Step 2: Apply the same fix in analytics/page.tsx**

Replace the equivalent while loop:
```typescript
        const allItems: Transaction[] = [];
        let cursor: string | undefined;
        let hasMore = true;

        while (hasMore) {
          const response = await accountsApi.getTransactions(session.access_token, {
            limit: 100,
            cursor,
          });
          allItems.push(...response.items);
          hasMore = response.has_more;
          cursor = response.next_cursor ?? undefined;
        }
```
with:
```typescript
        const allItems: Transaction[] = [];
        let cursor: string | undefined;
        let hasMore = true;
        const MAX_PAGES = 50;
        let pagesFetched = 0;

        while (hasMore && pagesFetched < MAX_PAGES) {
          const response = await accountsApi.getTransactions(session.access_token, {
            limit: 100,
            cursor,
          });
          allItems.push(...response.items);
          hasMore = response.has_more && !!response.next_cursor;
          cursor = response.next_cursor ?? undefined;
          pagesFetched++;
        }
```

**Step 3: TypeScript check**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 new type errors.

**Step 4: Commit**
```bash
git add apps/web/app/dashboard/page.tsx apps/web/app/dashboard/analytics/page.tsx
git commit -m "fix(frontend): add MAX_PAGES guard to pagination while loops

IMP-02: Unbounded loops could hang browser tab if API returns has_more=true
with null next_cursor. Now caps at 50 pages (5,000 transactions) and also
guards against has_more=true with missing cursor."
```

---

### Task 14: IMP-09 — Fix `token as string` TypeScript Lie

**Problem:** `SafeToSpendCard.tsx`, `TrainingJobCard.tsx`, and `insights/page.tsx` use `token as string` cast. If session is null/expired, `undefined` is passed as the Bearer token, sending `Authorization: Bearer undefined` to the API.

**Files:**
- Modify: `apps/web/components/dashboard/SafeToSpendCard.tsx` (line 23-25)
- Modify: `apps/web/components/dashboard/TrainingJobCard.tsx` (lines 18-21)
- Modify: `apps/web/app/dashboard/insights/page.tsx` (lines 137-139, 191-193)

**Step 1: Fix SafeToSpendCard.tsx**

Replace:
```typescript
      const token = session?.access_token;

      const result = await forecastApi.safeToSpend(token as string);
```
with:
```typescript
      if (!session?.access_token) {
        throw new Error('Session expired. Please sign in again.');
      }
      const result = await forecastApi.safeToSpend(session.access_token);
```

**Step 2: Fix TrainingJobCard.tsx**

Replace:
```typescript
      const token = session?.access_token;

      const latestJob = await trainingApi.getLatest(token as string);
```
with:
```typescript
      if (!session?.access_token) {
        setJob(null);
        return;
      }
      const latestJob = await trainingApi.getLatest(session.access_token);
```

**Step 3: Fix insights/page.tsx — forecast upload handler (around line 137)**

Replace:
```typescript
      const token = session?.access_token;

      const data = await forecastApi.predict(file, token as string);
```
with:
```typescript
      if (!session?.access_token) {
        throw new Error('Session expired. Please sign in again.');
      }
      const data = await forecastApi.predict(file, session.access_token);
```

**Step 4: Fix insights/page.tsx — training upload handler (around line 191)**

Replace:
```typescript
      const token = session?.access_token;

      const data = await trainingApi.upload(file, token as string, trainingPassword || undefined);
```
with:
```typescript
      if (!session?.access_token) {
        throw new Error('Session expired. Please sign in again.');
      }
      const data = await trainingApi.upload(file, session.access_token, trainingPassword || undefined);
```

**Step 5: TypeScript check**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 new type errors.

**Step 6: Commit**
```bash
git add apps/web/components/dashboard/SafeToSpendCard.tsx \
        apps/web/components/dashboard/TrainingJobCard.tsx \
        apps/web/app/dashboard/insights/page.tsx
git commit -m "fix(frontend): remove 'token as string' casts that silently passed undefined

IMP-09: If session expired between auth check and API call, undefined was
passed as Bearer token. Now explicitly checks for token presence and
throws/returns early with clear error message."
```

---

### Task 15: SUG-05 — Stop TrainingJobCard Polling on Terminal State

**Problem:** `TrainingJobCard` polls every 30 seconds indefinitely, even after job reaches `"completed"` or `"failed"` state.

**Files:**
- Modify: `apps/web/components/dashboard/TrainingJobCard.tsx` (lines 30-35)

**Step 1: Clear interval when terminal state is reached**

Replace:
```typescript
  useEffect(() => {
    fetchJob();
    // Poll every 30 seconds
    const interval = setInterval(fetchJob, 30000);
    return () => clearInterval(interval);
  }, [fetchJob]);
```
with:
```typescript
  useEffect(() => {
    fetchJob();
    const interval = setInterval(() => {
      // Stop polling when job reaches a terminal state
      if (job?.status === 'completed' || job?.status === 'failed') {
        clearInterval(interval);
        return;
      }
      fetchJob();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchJob, job?.status]);
```

**Step 2: TypeScript check**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npx tsc --noEmit 2>&1 | head -30
```

**Step 3: Commit**
```bash
git add apps/web/components/dashboard/TrainingJobCard.tsx
git commit -m "fix(frontend): stop TrainingJobCard polling when job reaches terminal state

SUG-05: Interval was never cleared after completed/failed status.
Now stops polling when job.status is 'completed' or 'failed'."
```

---

## BATCH 4 — Remaining Suggestions

---

### Task 16: SUG-01 — Floor safe_amount at Zero in forecasting

**Problem:** `safe_to_spend` can return a negative `safe_amount` for users who spend more than they earn. The concept of "safe to spend" implies a floor of zero.

**Files:**
- Modify: `apps/api/domains/forecasting/router.py` (line 163)

**Step 1: Apply floor**

Change:
```python
    safe_amount = round((avg_daily_income - avg_daily_spend) * horizon, 2)
```
to:
```python
    safe_amount = round(max(0.0, (avg_daily_income - avg_daily_spend) * horizon), 2)
    projected_overspend = round(max(0.0, (avg_daily_spend - avg_daily_income) * horizon), 2)
```

And update the return dict to include overspend info:
```python
    return {
        "safe_amount": safe_amount,
        "projected_overspend": projected_overspend,
        ...
    }
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/forecasting/ -v --tb=short
```

**Step 3: Commit**
```bash
git add apps/api/domains/forecasting/router.py
git commit -m "fix(forecasting): floor safe_amount at 0, add projected_overspend field

SUG-01: Negative safe_amount was confusing UX. Now floors at 0 and adds
projected_overspend field to separately communicate deficit scenarios."
```

---

### Task 17: SUG-08 — Remove Redundant get_user() in safe-to-spend

**Problem:** `safe-to-spend` endpoint calls `client.auth.get_user()` a second time at line 151, after all business logic, just to get `user_id` for TFT model lookup. This is a redundant Supabase Auth round-trip.

**Files:**
- Modify: `apps/api/domains/forecasting/router.py` (lines 109-152)

**Step 1: Extract user_id at the top of the function**

At the start of the `safe_to_spend` function body, after `horizon = 7`, add:
```python
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    user_id = user_response.user.id
```

Then remove the late `client.auth.get_user()` call at line 151-152:
```python
    # REMOVE these two lines:
    user_resp = client.auth.get_user()
    user_id = user_resp.user.id if user_resp and user_resp.user else None
```

**Step 2: Run tests**
```bash
python -m pytest apps/api/domains/forecasting/ -v --tb=short
```

**Step 3: Commit**
```bash
git add apps/api/domains/forecasting/router.py
git commit -m "fix(forecasting): move get_user() to top of safe-to-spend endpoint

SUG-08: Was calling get_user() redundantly at end of function after all
business logic. Now called once at top — auth fail-fast + no extra RTT."
```

---

### Task 18: IMP-04 — Remove Dead Frontend Code

**Problem:** Dead code from pre-migration client-side parsing left in `transactions/page.tsx` per `.gemini/current_state.md`: `classifyByKeywords`, `InsertTransaction` type, `parseFileRows`, Papa/XLSX imports.

**Files:**
- Modify: `apps/web/app/dashboard/transactions/page.tsx`

**Step 1: Read the file to identify dead code**
```bash
grep -n "classifyByKeywords\|InsertTransaction\|parseFileRows\|Papa\|XLSX\|papaparse\|xlsx" \
  "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web/app/dashboard/transactions/page.tsx"
```

**Step 2: Remove any identified dead imports and unused functions**

After identifying, remove:
- Unused `import Papa from 'papaparse'` or `import * as XLSX from 'xlsx'` if present
- Unused `classifyByKeywords` function if present
- Unused `InsertTransaction` type if present
- Unused `parseFileRows` function if present

**Step 3: TypeScript check**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npx tsc --noEmit 2>&1 | head -30
```
Expected: 0 errors.

**Step 4: Run frontend tests**
```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP/apps/web"
npm test -- --passWithNoTests 2>&1 | tail -20
```

**Step 5: Commit**
```bash
git add apps/web/app/dashboard/transactions/page.tsx
git commit -m "chore(frontend): remove dead client-side parsing code from transactions page

IMP-04: classifyByKeywords, InsertTransaction type, parseFileRows, and
associated CSV/XLSX imports were left over from pre-migration client-side
parsing. Frontend now uses API exclusively."
```

---

## Final Verification

After all tasks complete, run the full test suite:

```bash
cd "/Users/hassangameryt/Documents/Antigravity/SCALE APP"
source .venv/bin/activate
python -m pytest apps/api/ -v --tb=short 2>&1 | tail -30
```

Expected: All 122+ tests pass (any new tests added also pass).

```bash
cd apps/web
npx tsc --noEmit 2>&1 | head -20
npm test -- --passWithNoTests 2>&1 | tail -20
```

Expected: 0 TypeScript errors, all frontend tests pass.
