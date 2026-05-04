# BUG-020: Auto-enqueue storm when processing rows go stale

> **Doc ID:** BUG-020-auto-enqueue-storm-on-stuck-processing
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** High (operational — many duplicate training jobs queued)

## Symptom
`training_jobs` table accumulated many rows where `status='processing'` for the same user without ever transitioning to `completed` or `failed`. New `pending` rows kept being inserted by the auto-enqueue path despite an in-flight job.

## Root cause
`ForecastService._maybe_enqueue_training` checks for active jobs:

```python
active = supabase.table("training_jobs").select("id, logs").eq("user_id", user_id)
    .in_("status", ["pending", "queued", "running", "processing"]).limit(20).execute()
if any(str(row.get("logs") or "").startswith("forecasting:") for row in active.data):
    return
```

The marker `forecasting:autoenq` is set on INSERT but **the worker overwrites `logs`** with progress messages (`Fetching transactions...`, `Loaded N transactions...`, `Prepared M panel rows...`) the moment it claims the job. Once worker overwrites `logs`, the row no longer matches `startswith("forecasting:")`, so the active-job check returns false → enqueue fires again → storm.

Compounding: when training crashed mid-flight (BUG-B tz mismatch, fixed in `f37c55d`), the `processing` row never transitioned to `failed` because the exception path didn't update status. Stuck rows remained "active" forever.

## Fix
1. `_maybe_enqueue_training` skip on ANY active row for the user (regardless of `logs` prefix). Single-user prod doesn't need the prefix granularity; future multi-job-types will use a `job_type` column.
2. One-shot SQL to flip stuck `processing` rows older than 30 minutes → `failed` so the auto-enqueue check sees a clean slate.
3. Worker error path now writes `status='failed'` even when `train_model()` raises before the explicit `transition()` call (it already does, verifying).

## Regression prevention
- Add a Celery beat task `cleanup_stale_training_jobs` that flips `status='processing' AND updated_at < now() - 30 minutes` → `failed`. Already exists in `apps/api/core/tasks/maintenance_tasks.py` per CLAUDE.md ref.

## Refs
- `apps/api/domains/forecasting/service.py::_maybe_enqueue_training`
- `apps/worker/main.py::process_next_job`
