"""
TFT Training Pipeline.

Orchestrates the full training flow:
  fetch user transactions -> aggregate -> engineer features -> train TFT -> save checkpoint

Used by the background worker (apps/worker/main.py).
"""

import logging
import os

import lightning.pytorch as pl
import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet

from packages.forecasting.dataset import create_timeseries_dataset
from packages.forecasting.tft_model import create_tft_model

logger = logging.getLogger(__name__)

MINIMUM_DAYS = 90
MAX_PREDICTION_LENGTH = 30
MAX_ENCODER_LENGTH = 60


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def fetch_user_transactions(supabase, user_id: str) -> pd.DataFrame:
    """Fetch all transactions for a user (service-role client bypasses RLS).

    Per RFC-005 H2, the projection includes ``merchant_name`` so the
    heuristic recurrence detector can group on merchant. ``merchant`` is
    surfaced as the canonical column name downstream consumers use; we
    keep ``merchant_name`` available for rows where the upstream
    classifier wrote there.
    """
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
    if "merchant_name" in df.columns and "merchant" not in df.columns:
        df["merchant"] = df["merchant_name"]
    return df


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------


def run_training(
    enriched_df: pd.DataFrame,
    max_epochs: int = 30,
    early_stop_patience: int = 5,
    weight_decay: float = 0.0,
    batch_size: int = 64,
    learning_rate: float = 3e-4,
):
    """
    Create datasets, build TFT model, and train with PyTorch Lightning.

    Args:
        enriched_df:        Panel or single-series DataFrame with the
            standard time_idx/group_id features (RFC-005).
        max_epochs:         Lightning ``Trainer.max_epochs``. Default 30.
        early_stop_patience: ``EarlyStopping`` patience. Default 5.
        weight_decay:       L2 regularisation passed to the TFT optimiser
            via ``optimizer_params``. Default 0.0 (preserves production
            behaviour).
        batch_size:         DataLoader batch size for both train + val.
            Default 64 (preserves production behaviour).
        learning_rate:      TFT learning rate. Default 3e-4 (matches the
            RFC-006 §4 ``DEFAULT`` preset; previously was 0.01 — see the
            DEVIATION note in this module's RFC-006 changelog).

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

    train_dl = training_dataset.to_dataloader(train=True, batch_size=batch_size, num_workers=0)
    val_dl = validation_dataset.to_dataloader(train=False, batch_size=batch_size, num_workers=0)

    # Model — weight_decay forwarded into the BaseModel ``weight_decay``
    # field; default 0.0 leaves production behaviour unchanged.
    tft = create_tft_model(
        training_dataset,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
    )

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
