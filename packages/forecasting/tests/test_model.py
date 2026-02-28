import pandas as pd
import lightning.pytorch as pl
from packages.forecasting.dataset import TransactionLoader, create_timeseries_dataset
from packages.forecasting.tft_model import create_tft_model


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
