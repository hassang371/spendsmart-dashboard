# BUG-025: predict_with_tft never updated for panel-aware schema (RFC-005)

> **Doc ID:** BUG-025-predict-with-tft-panel-schema-mismatch
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Critical (TFT inference fails on every cache hit; ensemble path silently degrades to Chronos-only)

## Symptom

After the cache successfully loads the user's TFT model (post BUG-023 + BUG-024 fixes), inference fails with:

```
tft_inference_raised user_id=... error="'<' not supported between instances of 'float' and 'str'"
tft_inference_failed  user_id=... error="'<' not supported between instances of 'float' and 'str'"
```

`final_result = chronos_result` is taken every time. Ensemble blending and variable-importance extraction never run.

## Root cause

`predict_with_tft` (`packages/forecasting/inference.py`) was written for the **legacy single-series** training schema (single `group_id="main_user"` row per day). RFC-005 reshaped training to a **panel schema** with `group_ids=["user_id", "category_bucket"]` plus `bucket_total`, `month`, `scheduled_event_amount`. The trainer was migrated; the inference helper was not.

The model checkpoint was trained on the panel schema, so:
- `model.dataset_parameters` declares `static_categoricals=["user_id","category_bucket"]`
- `time_varying_known_categoricals` includes `month`
- `time_varying_known_reals` includes `scheduled_event_amount`
- `time_varying_unknown_reals` includes `bucket_total`

`predict_with_tft` builds `future_df` with only the legacy columns:

```python
future_df = pd.DataFrame({"date": future_dates})
future_df["time_idx"] = range(...)
future_df["group_id"] = history_df["group_id"].iloc[0]
future_df["day_of_week"] = ...; future_df["day_of_month"] = ...
future_df["is_payday"] = ...
future_df["daily_spend"] = 0.0; future_df["daily_income"] = 0.0; future_df["closing_balance"] = 0.0
combined_df = pd.concat([history_df, future_df], ignore_index=True)
```

The future rows are missing `user_id`, `category_bucket`, `bucket_total`, `month`, and `scheduled_event_amount`. After concat, those columns hold `NaN` (a `float`) in future rows but `str`/`category` in history rows. `TimeSeriesDataSet.from_dataset(reference_ds, combined_df, predict=True)` internally sorts/validates the panel keys and triggers a Python comparison between the float-NaN and the existing string category labels, raising:

> `'<' not supported between instances of 'float' and 'str'`

The error is caught, logged, and the path falls back to Chronos-only.

## Fix

Rebuild `future_df` to mirror the panel schema. For each `category_bucket` already in `history_df`, materialize `horizon` future rows with the full set of expected columns:

- Group keys: `user_id`, `category_bucket`, `group_id` (legacy alias)
- Time: `date`, `time_idx` (continued per group)
- Known categoricals: `day_of_week`, `day_of_month`, `month`, `is_payday`
- Known reals: `scheduled_event_amount` (default `0.0` — future rows have no scheduled event projected yet)
- Unknown reals (encoder-only, but column must exist for schema parity): `bucket_total`, `closing_balance`, `daily_spend`, `daily_income` (default `0.0`)
- Categoricals are coerced to the SAME `pd.Categorical` levels as in `history_df` so `pd.concat` preserves dtype.

`is_payday` for future days uses the same DOM heuristic the legacy path used (DOMs flagged as payday in history are flagged in future). Only computed once per bucket; unrelated buckets default to `"0"`.

The `closing_balance` field is `time_varying_unknown` per the dataset config, so its decoder values are unused — but the column must be present for `TimeSeriesDataSet` validation, so we keep it as `0.0`.

## Follow-up: NaN-from-Categorical → "Unknown category 'nan'"

The first cut of the fix used `pd.Categorical(future_df[col].astype(str), categories=hist_categories)` to align dtype. Any future value not present in `hist_categories` silently becomes `NaN`. pytorch-forecasting's `NaNLabelEncoder` later stringifies that `NaN` to the literal string `"nan"` and throws `Unknown category 'nan' encountered. Set add_nan=True to allow unknown categories`.

Final fix: skip the `pd.Categorical` cast entirely. Cast both `history_df` and `future_df` categorical columns to plain Python strings via `astype(str)`. `TimeSeriesDataSet.from_dataset` rebuilds its `NaNLabelEncoder` from `reference_ds` (built off `history_df`); since future values are deterministic functions of dates already present in `history_df`'s value space, encoder vocabulary covers them.

## Regression prevention

- Add a unit test that calls `predict_with_tft` against a dummy panel-schema model and asserts the response has 30 rows and no `error` key.
- Assert that `combined_df.dtypes` matches `history_df.dtypes` after the rebuild — guards against future column drift.

## Refs

- `packages/forecasting/inference.py::predict_with_tft`
- `packages/forecasting/dataset.py::create_timeseries_dataset` (panel branch, line 506)
- RFC-005 §3
- BUG-023, BUG-024 (predecessors that gated this bug from surfacing)
