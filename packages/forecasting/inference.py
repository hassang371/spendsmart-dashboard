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

    pred_ds = TimeSeriesDataSet.from_dataset(reference_ds, combined_df, predict=True, stop_randomization=True)

    # We predict for the specific group "0" (there is only one anyway)
    # The dataset should produce logic to cover the future if configured right.
    # By default `predict=True` prepares the dataset for the last available cutoff.

    pred_dl = pred_ds.to_dataloader(train=False, batch_size=64, num_workers=0)

    # Output shape: [n_groups, horizon, n_quantiles]. Panel mode: one
    # row per (user_id, category_bucket). Sum across buckets to get
    # the user-level total per day per quantile.
    raw_predictions = model.predict(pred_dl, mode="quantiles", return_x=False)
    raw_tensor = raw_predictions.detach().cpu().numpy()
    if raw_tensor.ndim == 3:
        preds = raw_tensor.sum(axis=0)  # shape [horizon, 7]
    else:
        preds = raw_tensor  # already [horizon, 7]

    # 5. Format results
    results = []
    quantiles = model.loss.quantiles  # [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]
    # We want P10, P50, P90.
    # indices: 0.1 is index 1, 0.5 is index 3, 0.9 is index 5.
    # verification needed on quantile indices. Default QuantileLoss quantiles are:
    # [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]

    q_map = {0.1: "p10", 0.5: "p50", 0.9: "p90"}
    q_indices = {q: i for i, q in enumerate(quantiles) if q in q_map}

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
        interpretation = model.interpret_output(raw_predictions, reduction="sum")

        weights = interpretation.get("encoder_variables", {})
        return [{"feature": k, "weight": round(float(v), 4)} for k, v in weights.items()]
    except Exception as e:
        logger.warning(f"Variable importance extraction failed: {e}")
        return None
