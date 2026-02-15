import pandas as pd
from packages.forecasting.dataset import TransactionLoader, create_timeseries_dataset
from pytorch_forecasting import TimeSeriesDataSet


def test_create_timeseries_dataset():
    # Setup dummy data with enough length for context
    # Need at least max_encoder_length + max_prediction_length
    # Let's say 30 context + 7 prediction = 37 points.
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

    # Create dataset
    ts_dataset = create_timeseries_dataset(
        enriched_df, max_encoder_length=30, max_prediction_length=7
    )

    # Assertions
    assert isinstance(ts_dataset, TimeSeriesDataSet)
    assert ts_dataset.target == "closing_balance"
    assert ts_dataset.time_idx == "time_idx"
    assert ts_dataset.group_ids == ["group_id"]
    assert "day_of_week" in ts_dataset.time_varying_known_categoricals
    assert "day_of_month" in ts_dataset.time_varying_known_categoricals
    assert "daily_income" in ts_dataset.time_varying_known_reals
    assert "daily_spend" in ts_dataset.time_varying_known_reals
