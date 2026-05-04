# BUG-029: Fan chart collapses to P50-only + variable importance always None

> **Doc ID:** BUG-029-fan-chart-collapses-and-variable-importance-broken
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** High (UX — chart looks broken; "What drives your forecast" permanently empty)

## Symptoms

1. Insights page renders only the P50 line — no P10/P90 fan, no inner band, no outer band. Chart looks like a single thin line instead of the designed three-band fan.
2. "What drives your forecast" panel always reads `Drivers not available for the population model.` even when the response carries a TFT model. Backend log shows `Variable importance extraction failed: tuple indices must be integers or slices, not str`.

## Root causes

### 1. Quantile crossing in ensemble output

`BalanceForecastChart.tsx` has a defensive guard:

```ts
const orderingOk = forecast.every(p =>
  p.p2 <= p.p10 && p.p10 <= p.p25 && p.p25 <= p.p50 &&
  p.p50 <= p.p75 && p.p75 <= p.p90 && p.p90 <= p.p98
);
```

When ANY single point in the horizon has crossed quantiles (e.g. `p2 > p10`), the entire fan is hidden and only the P50 line renders. The ensemble blender adds two engines' quantile outputs at different weights:

```python
point[key] = tft_weight * float(t[key]) + chronos_weight * float(c[key])
```

Each engine emits monotonic quantiles individually, but the per-key weighted sum can violate monotonicity at the seams (e.g. TFT noise on p2 lifting it above the blended p10). Pydantic's `ForecastPoint` schema doesn't enforce monotonicity, so the violation flows through to the wire.

### 2. `interpret_output` API change

pytorch-forecasting ≥1.0 returns a `Prediction` NamedTuple from `model.predict(..., mode="raw", return_x=True)` with attributes `output`, `x`, `y`, etc. The legacy code passed the whole tuple to `interpret_output`, which then tried to subscript it like a dict (`interpretation["encoder_variables"]`), raising `tuple indices must be integers or slices, not str`. The error was caught and silently downgraded to "no drivers".

## Fixes

### Fix 1 — Sort blended quantiles in `ensemble_forecasts`

After the weighted sum, sort the seven values in ascending order before assigning back to keys:

```python
values = sorted(
    tft_weight * float(t[key]) + chronos_weight * float(c[key])
    for key in QUANTILE_LABELS
)
for key, val in zip(QUANTILE_LABELS, values, strict=True):
    point[key] = round(val, 2)
```

This restores the QuantileLoss invariant. Sorting ≤7 floats per horizon day is negligible cost. The frontend's `orderingOk` check now passes; all three fan bands render.

### Fix 2 — Unwrap Prediction tuple in `extract_variable_importance`

Detect the NamedTuple, plain-tuple, and bare-tensor return shapes and pass the right object to `interpret_output`. Also handle both dict and NamedTuple shapes for the interpretation result, and both dict-of-floats and tensor encodings of `encoder_variables`:

```python
if hasattr(raw_predictions, "output") and hasattr(raw_predictions, "x"):
    inner = raw_predictions
elif isinstance(raw_predictions, tuple) and len(raw_predictions) >= 2:
    inner = SimpleNamespace(output=raw_predictions[0], x=raw_predictions[1])
else:
    inner = raw_predictions
interpretation = model.interpret_output(inner, reduction="sum")
weights_obj = interpretation["encoder_variables"] if isinstance(interpretation, dict) \
              else getattr(interpretation, "encoder_variables", {})
# Handle dict OR tensor-indexed-by-reference_ds.encoder_variables
```

## Regression prevention

- Add a unit test that constructs a TFT and a Chronos forecast where the per-quantile blend would produce crossing (e.g. TFT.p2 = 100, TFT.p10 = 10) and asserts the ensemble output is monotonic.
- Add a unit test that mocks `model.predict(...)` to return a `Prediction(output=..., x=...)` NamedTuple and asserts `extract_variable_importance` returns a non-empty list.
- Consider tightening the Pydantic `ForecastPoint` to a model_validator that asserts monotonicity (defense in depth).

## Refs

- `packages/forecasting/ensemble.py::ensemble_forecasts`
- `packages/forecasting/inference.py::extract_variable_importance`
- `apps/web/app/insights/components/BalanceForecastChart.tsx::orderingOk`
- LLD-011 §BalanceForecastChart
