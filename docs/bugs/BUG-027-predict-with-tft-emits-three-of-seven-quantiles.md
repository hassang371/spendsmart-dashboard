# BUG-027: predict_with_tft emits 3 quantiles; ensemble expects 7

> **Doc ID:** BUG-027-predict-with-tft-emits-three-of-seven-quantiles
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Critical (predict returns HTTP 500 when TFT inference succeeds)

## Symptom

After BUG-026 unblocked TFT inference, `/forecast/predict` returns 500:

```
KeyError: 'p2'
File "packages/forecasting/ensemble.py", line 55, in ensemble_forecasts
    tft_weight * float(t[key]) + chronos_weight * float(c[key]),
```

## Root cause

RFC-003 §3 contract specifies seven quantile levels per forecast point: `p2, p10, p25, p50, p75, p90, p98`. Chronos engine emits all seven (`QUANTILE_LABELS` in `chronos_engine.py`). `predict_with_tft` was still emitting only the legacy three-quantile output:

```python
q_map = {0.1: "p10", 0.5: "p50", 0.9: "p90"}
```

`ensemble_forecasts` iterates over chronos's keys (which carry all seven levels) and indexes into the TFT result with the same key — `t["p2"]` → KeyError.

This was a leftover from the pre-RFC-003 inference module. Stage 1 Task 4 added the seven-quantile blender + Stage 1 Task 3 added the seven-quantile chronos engine, but `predict_with_tft` was not migrated.

## Fix

Map all seven RFC-003 quantile levels in `q_map`. The model's `loss.quantiles` may not include every level (legacy 3-quantile checkpoints exist), so the fix also adds nearest-quantile fallback: when a target level isn't in the model's quantile list, use the closest available one.

```python
q_map = {0.02: "p2", 0.1: "p10", 0.25: "p25", 0.5: "p50", 0.75: "p75", 0.9: "p90", 0.98: "p98"}
quantiles_list = list(quantiles)
q_indices = {}
for q in q_map:
    if q in quantiles_list:
        q_indices[q] = quantiles_list.index(q)
    elif quantiles_list:
        q_indices[q] = min(range(len(quantiles_list)), key=lambda i: abs(quantiles_list[i] - q))
```

For freshly-trained models (which use the standard `QuantileLoss(quantiles=[0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98])`), every target level is exact. For legacy 3-quantile checkpoints, p2 falls back to p10's value, p25 to p10, p75 to p90, p98 to p90 — degraded but valid.

## Regression prevention

- Add a unit test that asserts `predict_with_tft` output has all seven keys (`p2, p10, p25, p50, p75, p90, p98`) when run against a fresh 7-quantile model.
- Consider an integration test that drives the full `/forecast/predict` path with a real ensemble cycle to catch contract drift between TFT/Chronos/ensemble end-to-end.

## Refs

- `packages/forecasting/inference.py::predict_with_tft`
- `packages/forecasting/chronos_engine.py::QUANTILE_LABELS`
- `packages/forecasting/ensemble.py::ensemble_forecasts`
- RFC-003 §3 (seven-quantile contract)
