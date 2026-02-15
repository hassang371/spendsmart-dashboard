import pytest
import pandas as pd
import numpy as np

from packages.forecasting.trainer import (
    detect_paydays,
    prepare_training_data,
)


def _make_daily_df(n_days: int, income_day: int = 1, income_amount: float = 50000):
    """Helper: build a simple daily DataFrame with a recurring payday."""
    dates = pd.date_range("2025-01-01", periods=n_days, freq="D")
    daily_income = np.zeros(n_days)
    daily_spend = np.random.uniform(500, 2000, n_days)

    # Put salary on the specified day_of_month for every month
    for i, d in enumerate(dates):
        if d.day == income_day:
            daily_income[i] = income_amount

    df = pd.DataFrame(
        {"daily_income": daily_income, "daily_spend": daily_spend},
        index=dates,
    )
    df.index.name = "date"
    return df


# ---------------------------------------------------------------------------
# detect_paydays
# ---------------------------------------------------------------------------


def test_detect_paydays_recurring():
    """Recurring large deposits on the same day_of_month are detected."""
    daily = _make_daily_df(120, income_day=1)
    is_payday = detect_paydays(daily)

    # Day 1 of each month should be flagged
    day1_mask = daily.index.day == 1
    assert is_payday[day1_mask].sum() >= 2
    # Non-payday days should be 0
    assert is_payday[~day1_mask].sum() == 0


def test_detect_paydays_no_income():
    """No income at all returns all zeros."""
    daily = pd.DataFrame(
        {"daily_income": np.zeros(60), "daily_spend": np.ones(60) * 100},
        index=pd.date_range("2025-01-01", periods=60, freq="D"),
    )
    daily.index.name = "date"
    is_payday = detect_paydays(daily)
    assert is_payday.sum() == 0


def test_detect_paydays_single_occurrence():
    """A large deposit that only occurs once is NOT marked as payday."""
    daily = pd.DataFrame(
        {"daily_income": np.zeros(60), "daily_spend": np.ones(60) * 100},
        index=pd.date_range("2025-01-01", periods=60, freq="D"),
    )
    daily.index.name = "date"
    # Single large deposit on Jan 15
    daily.iloc[14, daily.columns.get_loc("daily_income")] = 50000
    is_payday = detect_paydays(daily)
    assert is_payday.sum() == 0


# ---------------------------------------------------------------------------
# prepare_training_data
# ---------------------------------------------------------------------------


def _make_raw_transactions(n_days: int):
    """Helper: build raw transaction rows (date, amount) spanning n_days."""
    rows = []
    for i in range(n_days):
        date = pd.Timestamp("2025-01-01") + pd.Timedelta(days=i)
        # A few transactions per day
        rows.append({"date": date, "amount": -np.random.uniform(100, 500)})
        if np.random.random() > 0.7:
            rows.append({"date": date, "amount": np.random.uniform(200, 1000)})
        # Monthly salary
        if date.day == 1:
            rows.append({"date": date, "amount": 50000})
    return pd.DataFrame(rows)


def test_prepare_training_data_minimum_days():
    """ValueError raised when data spans fewer than MINIMUM_DAYS."""
    df = _make_raw_transactions(30)
    with pytest.raises(ValueError, match="Insufficient data"):
        prepare_training_data(df)


def test_prepare_training_data_success():
    """Full pipeline produces all expected columns."""
    df = _make_raw_transactions(120)
    enriched = prepare_training_data(df)

    expected_cols = [
        "date",
        "daily_income",
        "daily_spend",
        "closing_balance",
        "time_idx",
        "day_of_week",
        "day_of_month",
        "group_id",
        "is_payday",
    ]
    for col in expected_cols:
        assert col in enriched.columns, f"Missing column: {col}"

    # time_idx should be monotonically increasing
    assert enriched["time_idx"].is_monotonic_increasing
    # is_payday should be categorical
    assert enriched["is_payday"].dtype.name == "category"


def test_prepare_training_data_has_payday():
    """With regular monthly income, is_payday should flag at least some rows."""
    df = _make_raw_transactions(120)
    enriched = prepare_training_data(df)

    payday_count = (enriched["is_payday"] == "1").sum()
    assert payday_count > 0, "Expected at least one payday to be detected"
