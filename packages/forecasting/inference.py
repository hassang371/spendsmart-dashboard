"""
TFT Inference Module.

Handles loading models from Supabase Storage, caching them in memory,
and running predictions on new data.
"""

import io
import logging
from typing import Dict, Any, Optional

import pandas as pd
from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet

from packages.forecasting.trainer import (
    prepare_training_data,
    MAX_ENCODER_LENGTH,
)

logger = logging.getLogger(__name__)

# Simple in-memory cache: user_id -> loaded_model_object
_MODEL_CACHE: Dict[str, Any] = {}


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


def load_model(supabase, user_id: str) -> Optional[TemporalFusionTransformer]:
    """
    Load the TFT model for the user from Supabase Storage.
    Uses in-memory caching to avoid re-downloading on every request.
    """
    # Check cache first
    if user_id in _MODEL_CACHE:
        return _MODEL_CACHE[user_id]

    # Get path
    checkpoint_path = get_latest_checkpoint_path(supabase, user_id)
    if not checkpoint_path:
        logger.warning(f"No trained model found for user {user_id}")
        return None

    logger.info(f"Downloading checkpoint: {checkpoint_path}")

    # Download from Storage
    try:
        res = supabase.storage.from_("model-checkpoints").download(checkpoint_path)
        # res is binary content (bytes)
    except Exception as e:
        logger.error(f"Failed to download checkpoint {checkpoint_path}: {e}")
        return None

    # Load into PyTorch
    try:
        with io.BytesIO(res) as buffer:
            # map_location="cpu" is safer for inference servers
            tft = TemporalFusionTransformer.load_from_checkpoint(
                buffer, map_location="cpu"
            )
            tft.eval()
            tft.freeze()  # optimizing for inference
            _MODEL_CACHE[user_id] = tft
            return tft
    except Exception as e:
        logger.error(f"Failed to load model from bytes: {e}")
        return None


def invalidate_cache(user_id: str):
    """Clear the cached model for a user (e.g. after retraining)."""
    if user_id in _MODEL_CACHE:
        del _MODEL_CACHE[user_id]
        logger.info(f"Invalidated model cache for user {user_id}")


def predict_with_tft(
    model: TemporalFusionTransformer, df: pd.DataFrame, horizon: int = 30
) -> Dict[str, Any]:
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
        return {
            "error": f"Not enough history. Need {MAX_ENCODER_LENGTH} days, got {len(history_df)}."
        }

    # 2. Prepare future dataframe
    last_date = history_df["date"].max()
    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1), periods=horizon, freq="D"
    )

    future_df = pd.DataFrame({"date": future_dates})
    future_df["time_idx"] = range(
        history_df["time_idx"].max() + 1, history_df["time_idx"].max() + 1 + horizon
    )
    # Use same group_id as history for consistency with training
    future_df["group_id"] = history_df["group_id"].iloc[0]

    # Add calendar features
    future_df["day_of_week"] = (
        future_df["date"].dt.dayofweek.astype(str).astype("category")
    )
    future_df["day_of_month"] = future_df["date"].dt.day.astype(str).astype("category")

    # Handle is_payday for future
    # Simple heuristic: if day_of_month was a payday in history, assume it is in future
    # (This aligns with detect_paydays logic which flags specific days of month)
    # We need to re-run detection on history to see which DOMs are paydays
    # The 'history_df' already has 'is_payday' column.
    payday_doms = set(
        history_df[history_df["is_payday"] == "1"]["day_of_month"].astype(int).unique()
    )
    # Note: prepare_training_data converts day_of_month to int or str?
    # In trainer.py it converts to category. Let's check source logic.
    # It calls loader.enrich_features -> day_of_month is just date.day usually.
    # But later converted to category.
    # We can infer from 'date.day' directly.

    future_dom = future_df["date"].dt.day
    future_paydays = future_dom.isin(payday_doms).astype(int)
    future_df["is_payday"] = future_paydays.astype(str).astype("category")

    # Fill unknown targets with 0 (or NaN if handled) but TFT requires reals to be present?
    # Actually TFT uses targets for lag features. If we predict step-by-step or using encoder...
    # For 'daily_spend' and 'daily_income', we don't know them.
    # But for PREDICTION, we only need them for the *encoder* part (history).
    # The decoder (future) inputs are only known reals/categoricals.
    # We must ensure 'daily_spend' etc are in future_df but can be anything if not used in decoder?
    # Wait, if they are time_varying_unknown, they are NOT available in decoder.
    # So we don't strictly need them in future_df rows IF the model config knows they are unknown.
    # BUT PyTorch Forecast TimeSeriesDataSet usually expects compatible columns.
    # Let's fill with 0 to be safe and compatible with dataset structure.
    future_df["daily_spend"] = 0.0
    future_df["daily_income"] = 0.0
    future_df["closing_balance"] = 0.0  # This might be used as feature?
    # If closing_balance is used, 0 might trigger weird jumps.
    # Ideally simpler models don't use it. Our current model uses defaults from create_timeseries_dataset
    # which uses daily_spend and daily_income as unknown reals.

    # Concatenate
    combined_df = pd.concat([history_df, future_df], ignore_index=True)

    # 3. Create prediction dataset
    # We use predict(mode="quantiles") which handles the horizon automatically
    # provided we give it the encoder data.
    # Actually, the simplest way is to pass the LAST usable sequence from history
    # and ask it to predict 'horizon' steps.
    # We need to make sure the dataset knows about the future time steps.

    # method: use TimeSeriesDataSet.from_dataset(..., predict=True) on the NEW combined data
    # This creates samples. We want the sample that ends at the last known point.

    pred_ds = TimeSeriesDataSet.from_dataset(
        model.dataset_parameters, combined_df, predict=True, stop_randomization=True
    )

    # We predict for the specific group "0" (there is only one anyway)
    # The dataset should produce logic to cover the future if configured right.
    # By default `predict=True` prepares the dataset for the last available cutoff.

    pred_dl = pred_ds.to_dataloader(train=False, batch_size=1, num_workers=0)

    # 4. Predict
    # output: (n_samples, prediction_length, n_quantiles)
    # n_samples should be 1 if we only have 1 group and filtered correctly.
    raw_predictions = model.predict(pred_dl, mode="quantiles", return_x=False)

    # raw_predictions is a torch tensor
    # shape: [1, horizon, 7] (7 quantiles)

    preds = raw_predictions[0].detach().cpu().numpy()  # shape [horizon, 7]

    # 5. Format results
    results = []
    quantiles = model.loss.quantiles  # [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]
    # We want P10, P50, P90.
    # indices: 0.1 is index 1, 0.5 is index 3, 0.9 is index 5.
    # verification needed on quantile indices. Default QuantileLoss quantiles are:
    # [0.02, 0.1, 0.25, 0.5, 0.75, 0.9, 0.98]

    q_map = {0.1: "p10", 0.5: "p50", 0.9: "p90"}
    q_indices = {q: i for i, q in enumerate(quantiles) if q in q_map}

    for i in range(horizon):
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
