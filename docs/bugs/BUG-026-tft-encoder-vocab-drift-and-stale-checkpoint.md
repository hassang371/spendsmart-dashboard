# BUG-026: TFT inference fragile to encoder vocab drift; stale checkpoints never refresh

> **Doc ID:** BUG-026-tft-encoder-vocab-drift-and-stale-checkpoint
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Critical (every predict falls back to Chronos forever once a checkpoint goes stale)

## Symptom

After BUG-024 + BUG-025 fixes, every predict logs:

```
tft_inference_raised error="Unknown category '5' encountered. Set add_nan=True to allow unknown categories"
```

The trained TFT model exists, the cache loads it, but inference fails on every request. Frontend always shows `chronos` model tier; ensemble path never engages.

## Root cause (chain)

This is a chain of three compounding problems:

### Cause 1 — Stale checkpoint with truncated vocab (originating in BUG-021)

The latest `training_jobs` row was completed BEFORE the BUG-021 fix landed. Per BUG-021, `fetch_user_transactions` had no `.range()` call so PostgREST capped at the OLDEST 1000 transactions. The model was therefore trained on a tiny early-history window. Its saved `categorical_encoders` (e.g. `month`) only know the values that appeared in those 1000 rows.

For Hassan: most recent training spanned roughly mid-2023 only — encoder vocab for `month` is the small set of months covered by the first 1000 transactions, missing values like `"5"` (May).

### Cause 2 — Reference dataset rebuilt from current history doesn't help

`predict_with_tft` builds `reference_ds = create_timeseries_dataset(history_df)` from the CURRENT 1-year history slice. One might expect the fresh encoders to cover all 12 months — but `_build_dense_panel` only spans `min(date)..max(date)` of observed transactions. If the 1-year filter happens to start mid-month (e.g. `gte 2025-05-04T16:09:21`) and the user's first transaction in that window is later, the panel skips the months between the cutoff and the first transaction. So the fresh encoder ALSO lacks values that appear in the future horizon (which always covers 30 future days starting today).

The original `from_dataset(reference_ds, combined_df, predict=True)` call calls `encoder.transform(combined_df[col])`. Any value not in the encoder's `classes_` raises:

> `Unknown category 'X' encountered. Set add_nan=True to allow unknown categories`

### Cause 3 — No automatic recovery from stale checkpoint

Once the cache is warm with a stale model, `_maybe_enqueue_training` was guarded by `if cached is None`. Stale-but-loaded model meant `cached is not None`, which meant no auto-enqueue, which meant the bad checkpoint sat in cache forever (1h TTL, but reload would just download the same bad checkpoint again).

## Fix

Two-layer defense (immediate + durable):

### Layer 1 (immediate) — Defensive clamp in `predict_with_tft`

Before `from_dataset(reference_ds, combined_df, predict=True)` runs, walk every categorical column in `combined_df` and clamp values that aren't in the encoder's `classes_` vocab to a deterministic fallback (first vocab entry). Log how many rows were clamped + which values per column. This guarantees `encoder.transform` never raises, regardless of vocab drift.

```python
saved_encoders = getattr(reference_ds, "_categorical_encoders", {}) or {}
for col in categorical_cols:
    if col not in combined_df.columns or col not in saved_encoders:
        continue
    encoder = saved_encoders[col]
    classes = getattr(encoder, "classes_", None)
    if not classes:
        continue
    vocab = set(classes.keys()) if isinstance(classes, dict) else set(classes)
    series = combined_df[col].astype(str)
    unknown_mask = ~series.isin(vocab)
    if unknown_mask.any():
        fallback = next(iter(vocab))
        combined_df.loc[unknown_mask, col] = fallback
```

Side effect: clamped rows produce predictions using a different month's embedding. That's a small, bounded accuracy degradation — strictly better than falling back to Chronos-only.

### Layer 2 (durable) — Stale-checkpoint auto-recovery in `service.predict`

When TFT inference still fails (defense-in-depth catches whatever the clamp didn't), evict the cached entry and call `_maybe_enqueue_training`. The call is idempotent (skips if any active job already exists). The worker, now running with BUG-021 fixed, will retrain on the FULL history → fresh checkpoint with correct encoder vocab → next predict cycle resolves to ensemble.

```python
if "error" in tft_result:
    try:
        self.tft_cache.evict(user_id, reason="invalidation")
    except Exception:
        pass
    self._maybe_enqueue_training(user_id, days_of_data)
    final_result = chronos_result
```

## Why this is "fix once and for all"

| Failure mode | Layer 1 catches | Layer 2 catches |
|---|---|---|
| Reference encoder vocab missing future month | ✅ Clamp to fallback | — |
| Bucket sparse, missing day_of_month value | ✅ Clamp to fallback | — |
| Saved encoder `classes_` shape mismatch (corrupt ckpt) | — | ✅ Re-enqueue training |
| Future drift introduces new bucket name | ✅ Clamp to fallback | — |
| Pytorch-forecasting changes encoder API | — | ✅ Re-enqueue training |
| Permanent encoder vocab mismatch | ✅ Always succeeds with degraded-but-valid prediction | ✅ Eventually retrains |

Together: inference is bounded-success regardless of model state, AND the system self-heals over the next training cycle.

## Regression prevention

- Add a unit test that constructs a `predict_with_tft` call where future_df has a `month` value not in history → asserts no exception, asserts `forecast` length == horizon.
- Add a metric `tft_categorical_clamps_total` (label: `col`) so vocab drift is observable in Prometheus.
- Once the next training run completes against full history, the clamp should fire zero times — that's the long-term healthy state.

## Refs

- `packages/forecasting/inference.py::predict_with_tft`
- `apps/api/domains/forecasting/service.py::predict`
- BUG-021 (truncated training history — root of Cause 1)
- BUG-023, BUG-024, BUG-025 (predecessors that gated this bug from surfacing)
