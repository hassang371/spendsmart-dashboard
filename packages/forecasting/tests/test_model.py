import inspect

import lightning.pytorch as pl
import pandas as pd

from packages.forecasting.dataset import TransactionLoader, create_timeseries_dataset
from packages.forecasting.tft_model import create_tft_model


def test_create_tft_model_default_params_match_rfc005():
    """RFC-005 §"TFT hyperparameter supersession" — defaults are
    hidden_size=128, attention_head_size=8, lstm_layers=3,
    hidden_continuous_size=64.
    """
    params = inspect.signature(create_tft_model).parameters
    assert params["hidden_size"].default == 128
    assert params["attention_head_size"].default == 8
    assert params["lstm_layers"].default == 3
    assert params["hidden_continuous_size"].default == 64


def test_tft_training_loop():
    # 1. Setup minimal dummy data
    # Need enough points for context + prediction + splits
    # min_encoder=15, max_encoder=30, max_pred=7
    # Total day window: 50 days
    days = 50
    df = pd.DataFrame(
        {
            "date": pd.date_range(start="2026-01-01", periods=days, freq="D"),
            "amount": [10.0] * days,
        }
    )

    loader = TransactionLoader(df)
    daily_df = loader.aggregate_daily()
    enriched_df = loader.enrich_features(daily_df)

    # 2. Create Dataset and Dataloaders
    training_cutoff = enriched_df["time_idx"].max() - 7

    training = create_timeseries_dataset(
        enriched_df[lambda x: x.time_idx <= training_cutoff],
        max_encoder_length=30,
        max_prediction_length=7,
    )

    # Use to_dataloader
    train_dataloader = training.to_dataloader(train=True, batch_size=32, num_workers=0)

    # 3. Create Model
    tft = create_tft_model(training)

    # 4. Run Fast Dev Run (1 batch)
    trainer = pl.Trainer(
        fast_dev_run=True,
        accelerator="cpu",
        devices=1,
        enable_checkpointing=False,
        logger=False,
    )

    trainer.fit(tft, train_dataloaders=train_dataloader)
