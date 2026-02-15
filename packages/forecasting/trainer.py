"""
TFT Training Pipeline.

Orchestrates the full training flow:
  fetch user transactions -> aggregate -> engineer features -> train TFT -> save checkpoint

Used by the background worker (apps/worker/main.py).
"""

import os
import logging

import pandas as pd
import lightning.pytorch as pl
from pytorch_forecasting import TimeSeriesDataSet

from packages.forecasting.dataset import (
    TransactionLoader,
    create_timeseries_dataset,
)
from packages.forecasting.tft_model import create_tft_model

logger = logging.getLogger(__name__)

MINIMUM_DAYS = 90
MAX_PREDICTION_LENGTH = 30
MAX_ENCODER_LENGTH = 60


# ---------------------------------------------------------------------------
# Feature helpers
# ---------------------------------------------------------------------------


def detect_paydays(
    daily_df: pd.DataFrame, threshold_percentile: float = 90
) -> pd.Series:
    """
    Detect payday pattern: days with income above the 90th-percentile
    that recur on a similar day_of_month across >=2 months.

    Returns an integer Series (0/1) aligned with *daily_df* index.
    """
    if "daily_income" not in daily_df.columns:
        return pd.Series(0, index=daily_df.index)

    income = daily_df["daily_income"]
    positive_income = income[income > 0]

    if positive_income.empty:
        return pd.Series(0, index=daily_df.index)

    threshold = positive_income.quantile(threshold_percentile / 100)
    large_deposit = income >= threshold

    # Determine day-of-month for each row
    if isinstance(daily_df.index, pd.DatetimeIndex):
        dom = daily_df.index.day
    elif "date" in daily_df.columns:
        dom = pd.to_datetime(daily_df["date"]).dt.day
    else:
        return large_deposit.astype(int)

    # A day_of_month is a "payday" if it had large deposits in >=2 months
    payday_days = []
    for day in dom[large_deposit].unique():
        if large_deposit[dom == day].sum() >= 2:
            payday_days.append(day)

    is_payday = pd.Series(dom.isin(payday_days).astype(int), index=daily_df.index)
    return is_payday


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def fetch_user_transactions(supabase, user_id: str) -> pd.DataFrame:
    """Fetch all transactions for a user (service-role client bypasses RLS)."""
    response = (
        supabase.table("transactions")
        .select("transaction_date, amount, description, merchant_name, category")
        .eq("user_id", user_id)
        .order("transaction_date", desc=False)
        .execute()
    )

    if not response.data:
        raise ValueError(f"No transactions found for user {user_id}")

    df = pd.DataFrame(response.data)
    df = df.rename(columns={"transaction_date": "date"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)
    return df


def prepare_training_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full pipeline: aggregate daily -> validate history length -> add is_payday -> enrich features.

    Returns an enriched DataFrame ready for ``create_timeseries_dataset``.
    """
    loader = TransactionLoader(df)
    daily_df = loader.aggregate_daily()

    if len(daily_df) < MINIMUM_DAYS:
        raise ValueError(
            f"Insufficient data: {len(daily_df)} days available, "
            f"but the model requires at least {MINIMUM_DAYS}. "
            f"Please upload more transaction history."
        )

    # Payday detection
    daily_df["is_payday"] = detect_paydays(daily_df)

    # Standard time features
    enriched = loader.enrich_features(daily_df)

    # Ensure is_payday is a string categorical (required by TFT)
    enriched["is_payday"] = enriched["is_payday"].astype(str).astype("category")

    return enriched


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def run_training(
    enriched_df: pd.DataFrame,
    max_epochs: int = 30,
    early_stop_patience: int = 5,
):
    """
    Create datasets, build TFT model, and train with PyTorch Lightning.

    Returns ``(trainer, model, training_dataset)``.
    """
    training_cutoff = enriched_df["time_idx"].max() - MAX_PREDICTION_LENGTH

    training_data = enriched_df[enriched_df["time_idx"] <= training_cutoff].copy()
    validation_data = enriched_df.copy()

    if len(training_data) < MAX_ENCODER_LENGTH + MAX_PREDICTION_LENGTH:
        raise ValueError(
            f"Not enough training rows after split ({len(training_data)}). "
            f"Need at least {MAX_ENCODER_LENGTH + MAX_PREDICTION_LENGTH}."
        )

    # Datasets
    training_dataset = create_timeseries_dataset(
        training_data,
        max_encoder_length=MAX_ENCODER_LENGTH,
        max_prediction_length=MAX_PREDICTION_LENGTH,
    )

    validation_dataset = TimeSeriesDataSet.from_dataset(
        training_dataset,
        validation_data,
        predict=True,
        stop_randomization=True,
    )

    train_dl = training_dataset.to_dataloader(train=True, batch_size=64, num_workers=0)
    val_dl = validation_dataset.to_dataloader(train=False, batch_size=64, num_workers=0)

    # Model
    tft = create_tft_model(training_dataset, learning_rate=0.01)

    # Callbacks
    early_stop = pl.callbacks.EarlyStopping(
        monitor="val_loss",
        patience=early_stop_patience,
        mode="min",
    )

    checkpoint_cb = pl.callbacks.ModelCheckpoint(
        monitor="val_loss",
        mode="min",
        save_top_k=1,
        filename="tft-best-{val_loss:.4f}",
    )

    # Trainer
    trainer = pl.Trainer(
        max_epochs=max_epochs,
        accelerator="cpu",
        devices=1,
        callbacks=[early_stop, checkpoint_cb],
        gradient_clip_val=0.1,
        log_every_n_steps=10,
        enable_progress_bar=False,
        logger=False,
    )

    trainer.fit(tft, train_dataloaders=train_dl, val_dataloaders=val_dl)

    return trainer, tft, training_dataset


# ---------------------------------------------------------------------------
# Checkpoint persistence (Supabase Storage)
# ---------------------------------------------------------------------------


def save_checkpoint_to_supabase(supabase, trainer, user_id: str, job_id: str) -> str:
    """Upload the best checkpoint to Supabase Storage. Returns the storage path."""
    best_path = trainer.checkpoint_callback.best_model_path

    if not best_path or not os.path.exists(best_path):
        raise FileNotFoundError("No checkpoint file found after training")

    storage_path = f"checkpoints/{user_id}/{job_id}/tft_best.ckpt"

    with open(best_path, "rb") as f:
        data = f.read()

    supabase.storage.from_("model-checkpoints").upload(
        path=storage_path,
        file=data,
        file_options={"content-type": "application/octet-stream", "upsert": "true"},
    )

    logger.info(f"Checkpoint uploaded to {storage_path} ({len(data)} bytes)")
    return storage_path
