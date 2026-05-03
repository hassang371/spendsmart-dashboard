import numpy as np
import pandas as pd
import pytest

from packages.forecasting.dataset import TransactionLoader, prepare_training_data


def test_aggregate_daily_basics():
    # 1. Setup dummy data
    data = {
        "date": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-04"],
        "amount": [-50.00, -20.00, 1000.00, -10.00],
        "merchant": ["Walmart", "Uber", "Salary", "Coffee"],
    }
    df = pd.DataFrame(data)

    # 2. Initialize Loader
    loader = TransactionLoader(df)

    # 3. Aggregate
    daily_df = loader.aggregate_daily()

    # 4. Assertions
    assert "daily_spend" in daily_df.columns
    assert "daily_income" in daily_df.columns
    assert "closing_balance" in daily_df.columns

    # Check Jan 1st aggregation
    jan_1 = daily_df.loc["2026-01-01"]
    assert jan_1["daily_spend"] == 70.00  # 50 + 20
    assert jan_1["daily_income"] == 0.00

    # Check Jan 2nd (Income)
    jan_2 = daily_df.loc["2026-01-02"]
    assert jan_2["daily_income"] == 1000.00
    assert jan_2["daily_spend"] == 0.00

    # Check Jan 3rd (Missing date filling)
    jan_3 = daily_df.loc["2026-01-03"]
    assert jan_3["daily_spend"] == 0.00
    assert jan_3["daily_income"] == 0.00


def test_prepare_training_data_includes_payday_detection():
    """prepare_training_data should emit a panel with is_payday + features.

    Per RFC-005 §3 the canonical output is a panel: one row per
    (date, category_bucket). Number of rows = N days × 12 buckets.
    """
    rng = np.random.default_rng(42)
    dates = pd.date_range("2026-01-01", periods=100, freq="D")
    amounts = rng.choice([-50, -20, -10, 1000], size=100).astype(float)
    # Simulate payday on the 1st of each month so detection has >= 2 occurrences
    for i, d in enumerate(dates):
        if d.day == 1:
            amounts[i] = 5000.0

    df = pd.DataFrame({"date": dates, "amount": amounts})
    result = prepare_training_data(df)

    assert "is_payday" in result.columns
    assert "time_idx" in result.columns
    assert "day_of_week" in result.columns
    assert "day_of_month" in result.columns
    assert "category_bucket" in result.columns
    assert "user_id" in result.columns
    assert result["date"].nunique() == 100
    assert result["category_bucket"].nunique() == 12
    assert len(result) == 100 * 12
    # is_payday should be a string categorical (TFT requirement)
    assert result["is_payday"].dtype.name == "category"


def test_prepare_training_data_rejects_short_history():
    """prepare_training_data should raise ValueError when history < min_days."""
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    amounts = [-50.0] * 30
    df = pd.DataFrame({"date": dates, "amount": amounts})

    with pytest.raises(ValueError, match="Insufficient data"):
        prepare_training_data(df, min_days=90)


def test_prepare_training_data_no_min_days_check_by_default():
    """min_days=0 (default) should not enforce a minimum-length check."""
    dates = pd.date_range("2026-01-01", periods=30, freq="D")
    amounts = [-50.0] * 30
    df = pd.DataFrame({"date": dates, "amount": amounts})

    # Should not raise; panel = 30 days × 12 buckets
    result = prepare_training_data(df)
    assert result["date"].nunique() == 30
    assert result["category_bucket"].nunique() == 12
    assert len(result) == 30 * 12
