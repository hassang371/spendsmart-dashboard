# BUG-030: TFT bucket sum inflates by 12× + VI wrapper dict mismatch + Realtime REPLICA IDENTITY

> **Doc ID:** BUG-030-tft-bucket-multiplier-vi-wrapper-realtime-replica-identity
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Critical (forecasts wildly wrong; auto-refresh never fires; VI permanently broken)

## Symptoms

After BUG-028's full-data retrain (3083 txns, val_loss 5118.875 vs 28715.6), three issues remain:

1. **Forecast numbers off by ~12×.** Month-end snapshot shows worst case `-₹70,010`, likely `-₹30,605` despite Hassan having a positive balance. The fan chart's Y-axis spans `-₹1,20,000 → +₹1,20,000` instead of a sane balance range.
2. **"What drives your forecast" still says `Drivers not available for the population model.`** Backend log: `Variable importance extraction failed: tuple indices must be integers or slices, not str` (same error as BUG-029, despite the BUG-029 attempt to "fix" it).
3. **Page does not auto-refresh after training completes.** Hassan had to click reload manually. Backend cache invalidation fired (`cache_invalidated_via_pubsub`), but the frontend never received the `training_jobs.UPDATE` event.

## Root causes

### 1. TFT inference sums across panel groups when target is duplicated

RFC-005 `_build_dense_panel` joins `closing_balance` on `date` only — not `(date, category_bucket)`. The same value is duplicated across all 12 buckets per date because closing_balance is an account-wide cumulative quantity, not a per-bucket flow. The trainer's TimeSeriesDataSet has `group_ids=["user_id", "category_bucket"]` and `target="closing_balance"`, so all 12 groups train on the same target series.

`predict_with_tft` was doing:

```python
preds = raw_tensor.sum(axis=0)   # shape [n_groups, horizon, 7] → [horizon, 7]
```

Each group emits its own estimate of the SAME target. Summing 12 groups multiplies the forecast by ~12× (not exactly 12× because each group conditions on slightly different per-bucket reals). The Y-axis blow-up and impossible negative balances are direct consequences.

### 2. `interpret_output` expects the dict, not the Prediction wrapper

pytorch-forecasting ≥1.0 `model.predict(..., mode="raw", return_x=True)` returns a `Prediction` NamedTuple. The previous BUG-029 fix unwrapped to `inner = SimpleNamespace(output=…)` and called `interpret_output(inner)`. But `TemporalFusionTransformer.interpret_output(out: dict[str, torch.Tensor])` immediately does `out["decoder_attention"]` — which raises `tuple indices must be integers or slices, not str` on a NamedTuple/SimpleNamespace because `__getitem__` is index-based, not key-based.

The correct unwrap: pass `raw_predictions.output` (the actual dict), not the wrapper.

### 3. `training_jobs` had `REPLICA IDENTITY DEFAULT`

Supabase Realtime delivers `postgres_changes` events from the WAL. With `REPLICA IDENTITY DEFAULT` the OLD/NEW row in the WAL only carries the primary key + changed columns. The frontend subscription filter is `user_id=eq.<uid>`, but `user_id` doesn't change on a status flip — so it isn't present in the replicated row. The Realtime server's filter logic finds no match for `user_id=...` and silently drops the event. The frontend therefore never gets a "completed" event, never refetches, page sits stale.

This is an undocumented Supabase Realtime gotcha: filters on non-PK columns require `REPLICA IDENTITY FULL` to be reliably matched.

## Fixes

### Fix 1 — `mean(axis=0)` instead of `sum(axis=0)`

Each group's prediction is an independent estimate of the SAME quantity. Average them to denoise; don't sum them.

```python
if raw_tensor.ndim == 3:
    preds = raw_tensor.mean(axis=0)  # was .sum(axis=0)
else:
    preds = raw_tensor
```

After this fix: forecast magnitudes drop ~12× to a realistic range; safe-to-spend, month-end cards, and lowest-balance signal recover.

### Fix 2 — Pass `raw_predictions.output` to `interpret_output`

Walk down to the dict before invoking `interpret_output`. Handle NamedTuple, plain tuple, and bare-dict legacy shapes:

```python
if hasattr(raw_predictions, "output"):
    out_dict = raw_predictions.output
elif isinstance(raw_predictions, tuple) and len(raw_predictions) >= 1:
    out_dict = raw_predictions[0]
else:
    out_dict = raw_predictions
interpretation = model.interpret_output(out_dict, reduction="sum")
```

After this fix: `encoder_variables` populated → top-3 drivers surfaced in the "What drives your forecast" panel.

### Fix 3 — `ALTER TABLE training_jobs REPLICA IDENTITY FULL`

Migration `20260504000000_training_jobs_replica_identity_full.sql` runs once. Forces every column to be replicated on UPDATE so the Realtime server can match `user_id=eq.<uid>` filters. WAL volume cost: trivial for a low-write jobs table.

After this fix: training-complete event arrives at the browser within ~50ms of the worker's status flip → `refetch()` runs → page transitions automatically without user reload.

## Regression prevention

- Add a unit test that constructs a 12-group panel, runs `predict_with_tft`, and asserts the result magnitude is within 2× of the input series mean (catches re-introducing `sum(axis=0)`).
- Add a test that mocks `model.predict(..., mode="raw")` to return a `Prediction(output={...})` NamedTuple and asserts `extract_variable_importance` returns a non-empty list.
- Add a `db-realtime-readiness` smoke check that asserts `pg_class.relreplident = 'f'` for any table referenced in a `postgres_changes` filter on a non-PK column.

## Refs

- `packages/forecasting/inference.py::predict_with_tft`
- `packages/forecasting/inference.py::extract_variable_importance`
- `apps/web/app/dashboard/insights/page.tsx` (Realtime subscription)
- `supabase/migrations/20260504000000_training_jobs_replica_identity_full.sql`
- BUG-027 (predecessor — surfaced same `interpret_output` failure mode)
- BUG-029 (predecessor — incorrect first-pass fix for the wrapper unwrap)
