"""TFT inference helpers.

Stage 5 deletion: the legacy module-level ``_MODEL_CACHE`` dict + the
``load_model`` / ``invalidate_cache`` shims were removed in favour of
the bounded :class:`packages.forecasting.cache.TFTModelCache`. Callers
that previously wrote ``model = load_model(supabase, user_id)`` now use
``cached = await cache.get_or_load(user_id); model = cached.model``.

What remains in this module is pure inference math:
* :func:`get_latest_checkpoint_path` — used by the production
  ``default_supabase_loader`` to find a user's latest training-job row.
* :func:`predict_with_tft` — given a loaded model + history DataFrame,
  produce the seven-quantile forecast.
* :func:`extract_variable_importance` — Variable Selection Network
  weight extraction for ``ForecastInsights.primary_drivers``.

Refs: docs/bugs/BUG-018-tft-inference-cold-load-no-bounded-cache.md
Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md
"""

import logging
from typing import Any, Dict, Optional

import pandas as pd
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet

from packages.forecasting.dataset import create_timeseries_dataset, prepare_training_data
from packages.forecasting.trainer import MAX_ENCODER_LENGTH

logger = logging.getLogger(__name__)


def get_latest_checkpoint_path(supabase, user_id: str) -> Optional[str]:
    """Find the latest completed training job with a checkpoint."""
    try:
        response = (
            supabase.table("training_jobs")
            .select("checkpoint_path")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            path = response.data[0].get("checkpoint_path")
            if path:
                return path
    except Exception as e:
        logger.error(f"Error fetching latest checkpoint for {user_id}: {e}")
    return None


def predict_with_tft(model: TemporalFusionTransformer, df: pd.DataFrame, horizon: int = 30) -> Dict[str, Any]:
    """
    Run inference using the loaded model.

    Args:
        model: Loaded TFT model
        df: Historical transactions DataFrame (columns: date, amount, ...)
        horizon: Number of days to predict into the future (default 30)

    Returns:
        Dict with "forecast" list containing {date, p10, p50, p90} per day.
    """
    # 1. Prepare historical data (aggregation + features)
    try:
        history_df = prepare_training_data(df)
    except ValueError as e:
        logger.warning(f"Data preparation failed: {e}")
        return {"error": str(e)}

    if len(history_df) < MAX_ENCODER_LENGTH:
        return {"error": f"Not enough history. Need {MAX_ENCODER_LENGTH} days, got {len(history_df)}."}

    # Build future rows that match the panel schema produced by
    # ``aggregate_daily_panel`` (RFC-005). Per-bucket future rows so the
    # checkpoint's ``group_ids=[user_id, category_bucket]`` validates.
    last_date = history_df["date"].max()
    future_dates = pd.date_range(start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D")

    payday_doms = set(
        history_df[history_df["is_payday"].astype(str) == "1"]["day_of_month"].astype(str).astype(int).unique()
    )

    panel_groups = history_df[["user_id", "category_bucket"]].drop_duplicates().itertuples(index=False, name=None)

    future_blocks: list[pd.DataFrame] = []
    for user_id, bucket in panel_groups:
        bucket_hist = history_df[(history_df["user_id"] == user_id) & (history_df["category_bucket"] == bucket)]
        if bucket_hist.empty:
            continue
        last_time_idx = int(bucket_hist["time_idx"].max())
        block = pd.DataFrame(
            {
                "user_id": user_id,
                "category_bucket": bucket,
                "group_id": user_id,
                "date": future_dates,
                "time_idx": range(last_time_idx + 1, last_time_idx + 1 + horizon),
            }
        )
        block["day_of_week"] = block["date"].dt.dayofweek.astype(str)
        block["day_of_month"] = block["date"].dt.day.astype(str)
        block["month"] = block["date"].dt.month.astype(str)
        block["is_payday"] = block["date"].dt.day.isin(payday_doms).astype(int).astype(str)
        block["daily_spend"] = 0.0
        block["daily_income"] = 0.0
        block["closing_balance"] = 0.0
        block["bucket_total"] = 0.0
        block["scheduled_event_amount"] = 0.0
        future_blocks.append(block)

    if not future_blocks:
        return {"error": "No panel groups in history to project from."}

    future_df = pd.concat(future_blocks, ignore_index=True)

    # Cast both frames' categorical columns to plain strings before
    # concat. pd.Categorical(values, categories=hist_cats) silently
    # produces NaN for any value not in hist_cats, and pytorch-forecasting's
    # NaNLabelEncoder later stringifies that NaN to literal "nan" — which
    # fails encoding with "Unknown category 'nan'". Strings sidestep both
    # problems: TimeSeriesDataSet refits its NaNLabelEncoder from the
    # combined frame's actual values, future values are guaranteed to be
    # in vocabulary because reference_ds is rebuilt from history_df below.
    categorical_cols = ("user_id", "category_bucket", "group_id", "day_of_week", "day_of_month", "month", "is_payday")
    history_df = history_df.copy()
    for col in categorical_cols:
        if col in history_df.columns:
            history_df[col] = history_df[col].astype(str)
        if col in future_df.columns:
            future_df[col] = future_df[col].astype(str)

    combined_df = pd.concat([history_df, future_df], ignore_index=True)

    # 3. Create prediction dataset
    # We use predict(mode="quantiles") which handles the horizon automatically
    # provided we give it the encoder data.
    # Actually, the simplest way is to pass the LAST usable sequence from history
    # and ask it to predict 'horizon' steps.
    # We need to make sure the dataset knows about the future time steps.

    # method: use TimeSeriesDataSet.from_dataset(..., predict=True) on the NEW combined data
    # This creates samples. We want the sample that ends at the last known point.

    # 3. Create prediction dataset
    # BUG-004 fix: TimeSeriesDataSet.from_dataset() requires a TimeSeriesDataSet
    # *instance* as its first argument, not a dict.
    # model.dataset_parameters is a dict of constructor kwargs saved at training time.
    # We must rebuild a reference TimeSeriesDataSet from the history data using
    # those saved parameters, then use it as the template for from_dataset().

    try:
        # Rebuild the training-time reference dataset from history only.
        # We pass the saved parameters as overrides so the schema matches exactly.
        params = model.dataset_parameters  # dict of TimeSeriesDataSet kwargs
        reference_ds = create_timeseries_dataset(
            history_df,
            max_encoder_length=params.get("max_encoder_length", MAX_ENCODER_LENGTH),
            max_prediction_length=params.get("max_prediction_length", horizon),
        )
    except Exception as e:
        logger.error(f"Failed to reconstruct reference dataset for from_dataset: {e}")
        return {"error": f"Inference dataset construction failed: {e}"}

    # Defense-in-depth (BUG-026): clamp every categorical value in
    # combined_df to the encoder vocab before from_dataset runs. The
    # encoders were fitted on history_df, so any value not present in
    # history (e.g. a future month after a sparse history slice, a
    # bucket with limited day-of-month coverage) would raise
    # "Unknown category 'X'" and force fallback to Chronos.
    saved_encoders = getattr(reference_ds, "_categorical_encoders", {}) or {}
    for col in categorical_cols:
        if col not in combined_df.columns or col not in saved_encoders:
            continue
        encoder = saved_encoders[col]
        classes = getattr(encoder, "classes_", None)
        if not classes:
            continue
        vocab = set(classes.keys()) if isinstance(classes, dict) else set(classes)
        if not vocab:
            continue
        series = combined_df[col].astype(str)
        unknown_mask = ~series.isin(vocab)
        if unknown_mask.any():
            fallback = next(iter(vocab))
            unknown_values = series[unknown_mask].unique().tolist()
            logger.warning(
                "tft_inference_clamped_unknown_categoricals",
                extra={"col": col, "unknown": unknown_values, "fallback": fallback, "n_rows": int(unknown_mask.sum())},
            )
            combined_df.loc[unknown_mask, col] = fallback

    pred_ds = TimeSeriesDataSet.from_dataset(reference_ds, combined_df, predict=True, stop_randomization=True)

    # We predict for the specific group "0" (there is only one anyway)
    # The dataset should produce logic to cover the future if configured right.
    # By default `predict=True` prepares the dataset for the last available cutoff.

    pred_dl = pred_ds.to_dataloader(train=False, batch_size=64, num_workers=0)

    # Output shape: [n_groups, horizon, n_quantiles]. Panel mode: one
    # row per (user_id, category_bucket). The training target is
    # ``closing_balance`` which RFC-005 explicitly DUPLICATES across
    # all 12 buckets per date (account-wide cumulative balance, not a
    # per-bucket flow). Each group's prediction is therefore an
    # estimate of the SAME quantity. We average across groups to
    # produce a single user-level forecast — summing would inflate the
    # forecast by ~12× and was the cause of the wildly negative
    # WORST/LIKELY card numbers Hassan reported.
    raw_predictions = model.predict(pred_dl, mode="quantiles", return_x=False)
    raw_tensor = raw_predictions.detach().cpu().numpy()
    if raw_tensor.ndim == 3:
        preds = raw_tensor.mean(axis=0)  # shape [horizon, 7]
    else:
        preds = raw_tensor  # already [horizon, 7]

    # Anchor the forecast to the user's CURRENT balance so day-0 P50
    # equals the last observed closing_balance. Without this shift the
    # forecast carries the model's absolute-level offset (which can
    # drift from reality if the panel's cumulative-balance baseline
    # has decoupled from the user's actual account balance — common
    # when transactions partially populated history). The user reads
    # "balance forecast" as "where my balance goes from today"; the
    # raw model prediction is "where the trained-target trajectory
    # goes from its own t=0". Shifting reconciles the two.
    try:
        last_closing = float(history_df["closing_balance"].iloc[-1])
        _quantiles_for_anchor = list(model.loss.quantiles)
        if 0.5 in _quantiles_for_anchor:
            p50_col = _quantiles_for_anchor.index(0.5)
            shift = last_closing - float(preds[0, p50_col])
            preds = preds + shift
    except Exception as _exc:
        logger.warning(f"forecast_anchor_shift_failed: {_exc}")

    # 5. Format results
    results = []
    quantiles = model.loss.quantiles  # [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]
    # We want P10, P50, P90.
    # indices: 0.1 is index 1, 0.5 is index 3, 0.9 is index 5.
    # verification needed on quantile indices. Default QuantileLoss quantiles are:
    # [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]

    # RFC-003 contract: emit all seven quantiles so ensemble_forecasts
    # can blend each level with chronos. Falls back to nearest available
    # quantile when training used fewer levels (e.g. legacy 3-quantile
    # checkpoints).
    q_map = {0.02: "p2", 0.1: "p10", 0.25: "p25", 0.5: "p50", 0.75: "p75", 0.9: "p90", 0.98: "p98"}
    quantiles_list = list(quantiles)
    q_indices = {}
    for q in q_map:
        if q in quantiles_list:
            q_indices[q] = quantiles_list.index(q)
        elif quantiles_list:
            q_indices[q] = min(range(len(quantiles_list)), key=lambda i: abs(quantiles_list[i] - q))

    actual_length = min(horizon, len(preds))
    for i in range(actual_length):
        date = future_dates[i]
        row_preds = preds[i]

        entry = {"date": date.strftime("%Y-%m-%d")}
        for q, label in q_map.items():
            if q in q_indices:
                val = float(row_preds[q_indices[q]])
                entry[label] = val  # Allow negative values for overdraft forecasting
            else:
                # Fallback if quantile not found?
                entry[label] = 0.0

        results.append(entry)

    return {
        "forecast": results,
        "model_version": "tft_v1",  # placeholder
        "horizon": horizon,
    }


def extract_variable_importance(
    model: TemporalFusionTransformer,
    df: pd.DataFrame,
) -> list[dict[str, float]] | None:
    """Extract variable importance from a TFT model via ``interpret_output``.

    Returns a list of ``{"feature": name, "weight": float}`` dicts on success,
    or ``None`` if the model cannot produce an interpretation (e.g. history
    shorter than the encoder length, or any internal failure).
    """
    try:
        history_df = prepare_training_data(df)
        if len(history_df) < MAX_ENCODER_LENGTH:
            return None

        params = model.dataset_parameters
        reference_ds = create_timeseries_dataset(
            history_df,
            max_encoder_length=params.get("max_encoder_length", MAX_ENCODER_LENGTH),
            max_prediction_length=params.get("max_prediction_length", 30),
        )
        pred_dl = reference_ds.to_dataloader(train=False, batch_size=64, num_workers=0)

        raw_predictions = model.predict(pred_dl, mode="raw", return_x=True)
        # pytorch-forecasting >=1.0 returns a Prediction NamedTuple
        # (output, x, y, decoder_lengths, ...). interpret_output expects
        # the underlying *dict* (out["decoder_attention"], etc.), not
        # the NamedTuple wrapper, otherwise it raises
        # "tuple indices must be integers" trying to subscript by str.
        if hasattr(raw_predictions, "output"):
            out_dict = raw_predictions.output
        elif isinstance(raw_predictions, tuple) and len(raw_predictions) >= 1:
            out_dict = raw_predictions[0]
        else:
            out_dict = raw_predictions
        interpretation = model.interpret_output(out_dict, reduction="sum")
        # interpret_output may return either a dict or a NamedTuple
        # depending on version. Handle both.
        if isinstance(interpretation, dict):
            weights_obj = interpretation.get("encoder_variables", {})
        else:
            weights_obj = getattr(interpretation, "encoder_variables", {})
        # encoder_variables can be a dict {feature: weight} OR a torch
        # tensor indexed by reference_ds.encoder_variables. Normalise.
        if hasattr(weights_obj, "items"):
            pairs = list(weights_obj.items())
        else:
            try:
                feature_names = reference_ds.encoder_variables  # list[str]
                values = weights_obj.detach().cpu().numpy() if hasattr(weights_obj, "detach") else weights_obj
                pairs = list(zip(feature_names, values, strict=False))
            except Exception:
                pairs = []
        return [{"feature": str(k), "weight": round(float(v), 4)} for k, v in pairs]
    except Exception as e:
        logger.warning(f"Variable importance extraction failed: {e}")
        return None
