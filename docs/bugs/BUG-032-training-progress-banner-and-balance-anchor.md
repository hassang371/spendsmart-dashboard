# BUG-032: No "training in progress" feedback + forecast not anchored to current balance

> **Doc ID:** BUG-032-training-progress-banner-and-balance-anchor
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Medium (UX clarity — both findings make the page feel broken when it isn't)

## Symptoms

1. When the auto-enqueue path fires (cold-start user, stale checkpoint recovery), the frontend silently shows the chronos-only forecast with no signal that a personalised model is being trained in the background. Users can't tell if the page is loading, broken, or working — they just stare at the same numbers for 5 minutes wondering why nothing changed.
2. The balance forecast Y-axis numbers feel disconnected from the user's actual balance. Hassan reads "balance forecast" as "where MY balance goes from today"; the model emits "where the trained-target trajectory goes from its own t=0", which is offset from the user's true current balance because `closing_balance` is cumulative-from-min-date.

## Root causes

### 1. ColdStartBanner only checked `model_type === 'chronos2' || confidence === 'low'`

It never queried `training_jobs` to see whether a personalised model was actually being trained. So:
- "Cold-start, no model yet, training queued" — looked identical to —
- "User permanently capped at chronos2 (insufficient history)" — even though the first state should clearly say "training in progress, ETA X minutes".

### 2. `predict_with_tft` returned absolute trajectory levels

The model trained on `closing_balance` (cumulative net inflow/outflow since `min_date`). At inference, day-0 of the forecast horizon is wherever the trained trajectory's level happens to be. That level is offset from the user's intuitive "current balance" because:
- `closing_balance.iloc[0]` starts at the first day's net change, not the user's true opening balance.
- Cumulative drift over years can compound model bias.

The forecast was correct in shape but Y-axis numbers were misaligned with the user's mental model.

## Fixes

### Fix 1 — ColdStartBanner subscribes to `training_jobs` Realtime

The banner now:
- Reads the latest in-flight `training_jobs` row for the current user on mount (initial snapshot).
- Subscribes to `postgres_changes (event='*', filter=user_id=eq.<uid>)` so any status flip pushes a new state without polling.
- Renders three distinct messages:
  - `processing/running` → blue banner: "Training your personalised model now… ETA 3–5 minutes on M-series. Refreshes automatically."
  - `pending/queued` → blue banner: "Personalised model queued for training."
  - idle (no in-flight job) but still cold-start → original amber banner.

REPLICA IDENTITY FULL on `training_jobs` (BUG-030 migration) ensures the per-user filter resolves so updates actually reach the browser.

### Fix 2 — Anchor forecast to last observed `closing_balance`

After computing the panel-mean prediction matrix `[horizon, 7]`, shift the entire matrix by:

```python
last_closing = float(history_df["closing_balance"].iloc[-1])
p50_col = quantiles_list.index(0.5)
shift = last_closing - float(preds[0, p50_col])
preds = preds + shift
```

Day-0 P50 now equals the user's last observed balance. Quantile spreads (P50–P10, P90–P50) are preserved because we shift uniformly. The forecast literally answers "where does my balance go from today?" — the user's actual question.

## Regression prevention

- Update existing `test_predict_with_tft` to assert quantile SPREADS (shift-invariant) rather than absolute values.
- Add a test that mocks `history_df["closing_balance"].iloc[-1] = 50000` and asserts `forecast[0]["p50"] ≈ 50000` regardless of raw model output.
- Add a frontend integration test that mounts `ColdStartBanner` while a `processing` row exists and asserts the "Training… ETA 3–5 min" copy renders.

## Refs

- `apps/web/app/insights/components/ColdStartBanner.tsx`
- `packages/forecasting/inference.py::predict_with_tft` (anchor block)
- `packages/forecasting/tests/test_inference.py::test_predict_with_tft` (assertion update)
- BUG-030 (REPLICA IDENTITY FULL — prerequisite for the banner subscription)
