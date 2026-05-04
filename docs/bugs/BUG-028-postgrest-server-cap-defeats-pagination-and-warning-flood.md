# BUG-028: PostgREST server cap silently defeats trainer pagination + backend warning flood + missing training_jobs metadata

> **Doc ID:** BUG-028-postgrest-server-cap-defeats-pagination-and-warning-flood
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** High (TFT trains on 32% of available data; backend log unreadable; observability columns NULL)

## Symptoms

Three independent issues observed against the same restart:

1. **Trainer log says `Loaded 1000 transactions`** while a direct SQL count returns 3083 rows for the same user (`2023-05-08 → 2026-04-16`, ~3 years of data). Despite the BUG-021 fix using `.range(0, 9999)`, the trainer only ingested 1000 rows → TFT trained on the OLDEST third of the user's history.
2. **Backend log flooded with `UserWarning: X does not have valid feature names`** on every `/forecast/predict`. Tens of thousands of duplicate lines per request — Hassan reported the terminal was unreadable.
3. **`training_jobs` row has NULL** for `date_range_start`, `date_range_end`, `source_row_count`, and `data_fingerprint`. Worker's writeback only set `checkpoint_path`, `metrics`, and `transaction_count`.

## Root causes

### 1. PostgREST server-side `db-max-rows` cap

Supabase ships PostgREST with `db-max-rows = 1000` as the project default. This is a SERVER-SIDE cap: when a client sends `Range: 0-9999` the server still returns at most 1000 rows. The trainer's pagination loop then sees `len(batch) = 1000 < page_size = 10000` and exits — false-positive end-of-stream.

```python
page_size = 10_000
while True:
    end = start + page_size - 1
    batch = supabase.table("transactions").range(start, end).execute().data or []
    rows.extend(batch)
    if len(batch) < page_size:   # ← fires after the server-cap-truncated first page
        break
```

This is the same data-truncation pattern as BUG-021, just one layer deeper.

### 2. Backend missing warning suppression

`apps/worker/main.py` already filters the sklearn `StandardScaler` "X does not have valid feature names" UserWarning (it fires per-batch inside `TimeSeriesDataSet`'s scaler application). The same TFT inference path now runs INSIDE the FastAPI process via `predict_with_tft`, but `apps/api/main.py` had no equivalent `warnings.filterwarnings` call. Every predict triggers thousands of warning lines.

### 3. Worker writeback omits half the schema

`training_jobs` schema has six observability columns: `metrics`, `transaction_count`, `source_row_count`, `date_range_start`, `date_range_end`, `data_fingerprint`. Worker only set `metrics` + `transaction_count`. The other four were never written → permanently NULL → no way to detect data drift, dataset reuse, or tie a checkpoint back to a specific date window.

## Fixes

### Fix 1 — `page_size = 1000`

Match the server cap so each `.range(start, start + 999)` request consumes exactly one server response, and the loop's `len(batch) < page_size` exit only fires on the genuine last page:

```python
page_size = 1_000
```

For Hassan: 4 round-trips (1000 + 1000 + 1000 + 83 = 3083 rows). Pagination is independent of any server-side `db-max-rows` value going forward.

### Fix 2 — Suppress backend warnings

Add the same `warnings.filterwarnings` block at the TOP of `apps/api/main.py` (before any sklearn / pytorch-forecasting import). Mirrors the worker filters:

- `X does not have valid feature names` (sklearn StandardScaler, per-batch)
- `isinstance(treespec, LeafSpec) is deprecated` (Lightning, per-batch)
- `The 'predict_dataloader' does not have many workers` (Lightning, per-predict)
- `Not all dimensions are equal for tensors shapes` (pytorch-forecasting interpret_output, per-VI extraction)

### Fix 3 — Wire the missing training_jobs columns

Worker writeback now computes:
- `date_range_start` = `df["date"].min().date().isoformat()`
- `date_range_end` = `df["date"].max().date().isoformat()`
- `data_fingerprint` = `sha256(user_id|date_min|date_max|tx_count)` — stable hash so duplicate training runs on identical input data are detectable post-hoc.
- Also corrected `metrics.days_of_data` to be DISTINCT DAYS (`enriched["date"].nunique()`), not panel rows. New `metrics.panel_rows` separately captures `len(enriched)`.

`source_row_count` stays NULL for forecasting jobs by design — the column is reserved for adapter-training jobs that ingest from `training_corrections`.

## Regression prevention

- Add an integration test that seeds 2500+ transactions and asserts `fetch_user_transactions` returns exactly that many rows (catches any future server cap regression).
- Add a unit test that asserts every forecast `training_jobs` row has non-NULL `date_range_start` / `date_range_end` / `data_fingerprint` after a successful run.
- Document in `docs/design/forecasting.md` that PostgREST server cap is the binding limit, not the client `.range()` size.

## Refs

- `packages/forecasting/trainer.py::fetch_user_transactions`
- `apps/worker/main.py` (writeback + hashlib import)
- `apps/api/main.py` (warning filters)
- BUG-021 (predecessor — same data-truncation pattern, client-side)
