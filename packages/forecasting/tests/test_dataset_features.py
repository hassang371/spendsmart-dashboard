import pandas as pd
from packages.forecasting.dataset import TransactionLoader


def test_enrich_features():
    # Setup dummy data
    df = pd.DataFrame(
        {
            "date": pd.date_range(start="2026-01-01", periods=10, freq="D"),
            "amount": [10.0] * 10,
        }
    )

    loader = TransactionLoader(df)
    # We assume aggregate_daily handles the aggregation first
    daily_df = loader.aggregate_daily()

    # New method to implementation
    enriched_df = loader.enrich_features(daily_df)

    # Assertions
    assert "time_idx" in enriched_df.columns
    assert "day_of_week" in enriched_df.columns
    assert "day_of_month" in enriched_df.columns
    assert "group_id" in enriched_df.columns

    # Check time_idx monotonicity
    assert enriched_df["time_idx"].is_monotonic_increasing
    assert enriched_df["time_idx"].iloc[0] == 0
    assert enriched_df["time_idx"].iloc[1] == 1

    # Check group_id is constant
    assert enriched_df["group_id"].nunique() == 1
    assert enriched_df["group_id"].iloc[0] == "main_user"
