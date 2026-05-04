"""Tests for ``packages/forecasting/insights.py`` (RFC-003 §2).

Pure unit tests — no DB, no HTTP, no PyTorch model. Synthetic
``forecast_matrix`` numpy arrays + small ``history_df`` DataFrames.

The 17-test list mirrors ``docs/plans/2026-04-06-prediction-engine.md::Task 6.5``.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §2
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_forecast_matrix(horizon: int = 30, seed: int = 0) -> np.ndarray:
    """Synthetic 7-quantile forecast matrix shaped ``(horizon, 7)``.

    Quantile order: ``[p2, p10, p25, p50, p75, p90, p98]``. Values are
    monotonically non-decreasing across columns within each row so the
    matrix represents a valid distribution.
    """
    rng = np.random.default_rng(seed)
    median = rng.normal(loc=10_000.0, scale=500.0, size=horizon)
    spread = np.array([-2000, -1000, -500, 0, 500, 1000, 2000])
    return np.column_stack([median + s for s in spread])


def _make_history_df(n_days: int = 90, base_balance: float = 5000.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rng = np.random.default_rng(0)
    closing = base_balance + rng.normal(loc=0.0, scale=200.0, size=n_days).cumsum()
    return pd.DataFrame({"date": dates, "closing_balance": closing})


def _future_dates(start: date, horizon: int = 30) -> list[date]:
    return [start + timedelta(days=i) for i in range(1, horizon + 1)]


# ---------------------------------------------------------------------------
# Module-level constant
# ---------------------------------------------------------------------------


def test_insights_version_constant_exported():
    """The module exports ``INSIGHTS_VERSION`` = "v1"."""
    from packages.forecasting import insights

    assert hasattr(insights, "INSIGHTS_VERSION")
    assert insights.INSIGHTS_VERSION == "v1"


# ---------------------------------------------------------------------------
# derive_floor
# ---------------------------------------------------------------------------


def test_derive_floor_uses_p10_of_history():
    """Floor = P10 of historical closing_balance, source=auto_p10_history."""
    from packages.forecasting.insights import derive_floor

    history = pd.DataFrame({"closing_balance": list(range(100))})  # 0..99
    floor, source = derive_floor(history)
    # numpy quantile of 0..99 at 0.10 ≈ 9.9
    assert source == "auto_p10_history"
    assert floor == pytest.approx(9.9, abs=0.5)


def test_derive_floor_honours_user_override():
    """When user_override is supplied, return it verbatim and source=user_override."""
    from packages.forecasting.insights import derive_floor

    history = pd.DataFrame({"closing_balance": list(range(100))})
    floor, source = derive_floor(history, user_override=1234.5)
    assert source == "user_override"
    assert floor == pytest.approx(1234.5)


def test_derive_floor_clamps_at_zero():
    """Negative P10 (always-negative balance user) → clamped to 0."""
    from packages.forecasting.insights import derive_floor

    history = pd.DataFrame({"closing_balance": [-500, -400, -300, -200, -100]})
    floor, source = derive_floor(history)
    assert source == "auto_p10_history"
    assert floor == 0.0


# ---------------------------------------------------------------------------
# compute_insights — shape + edge cases
# ---------------------------------------------------------------------------


def test_compute_insights_emits_ten_fields():
    """Returned ForecastInsights must carry all RFC-003 §1 fields."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    history = _make_history_df()
    futures = _future_dates(date(2026, 4, 1))

    out = compute_insights(matrix, futures, history, variable_importance=None)

    assert hasattr(out, "lowest_balance")
    assert hasattr(out, "month_end")
    assert hasattr(out, "predicted_monthly_spend")
    assert hasattr(out, "predicted_monthly_income")
    assert hasattr(out, "confidence_band_width")
    assert hasattr(out, "primary_drivers")
    assert hasattr(out, "safe_to_spend")
    assert hasattr(out, "overdraft_risk_score")
    assert hasattr(out, "floor_used")
    assert hasattr(out, "floor_source")


def test_lowest_balance_picks_min_p10_day():
    """``lowest_balance`` reports the day where P10 is minimised."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    # Force day 7 to have the lowest P10
    matrix[6, 1] = -99_999.0
    matrix[6, 3] = -50_000.0  # also P50 anchor for that day
    futures = _future_dates(date(2026, 4, 1))
    history = _make_history_df()

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.lowest_balance.p10 == pytest.approx(matrix[6, 1])
    expected_date = (date(2026, 4, 1) + timedelta(days=7)).strftime("%Y-%m-%d")
    assert out.lowest_balance.date == expected_date


def test_month_end_is_day_30_of_horizon():
    """``month_end`` reports the *last* day of the horizon (rolling 30, not calendar)."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix(horizon=30)
    futures = _future_dates(date(2026, 4, 1), horizon=30)
    history = _make_history_df()

    out = compute_insights(matrix, futures, history, variable_importance=None)

    # Index 29 = day 30
    assert out.month_end.p10 == pytest.approx(matrix[29, 1])
    assert out.month_end.p50 == pytest.approx(matrix[29, 3])
    assert out.month_end.p90 == pytest.approx(matrix[29, 5])


def test_predicted_monthly_spend_sums_negative_p50_deltas():
    """Monthly spend = sum of negative day-over-day P50 deltas (absolute value)."""
    from packages.forecasting.insights import compute_insights

    # Construct 3-day forecast with P50: [100, 90, 80] → deltas -10, -10 → spend 20
    matrix = np.zeros((3, 7))
    matrix[:, 3] = [100.0, 90.0, 80.0]  # P50 column
    futures = _future_dates(date(2026, 4, 1), horizon=3)
    history = _make_history_df()

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.predicted_monthly_spend == pytest.approx(20.0)


def test_predicted_monthly_income_sums_positive_p50_deltas():
    """Monthly income = sum of positive day-over-day P50 deltas."""
    from packages.forecasting.insights import compute_insights

    matrix = np.zeros((3, 7))
    matrix[:, 3] = [100.0, 110.0, 130.0]  # deltas +10, +20 → income 30
    futures = _future_dates(date(2026, 4, 1), horizon=3)
    history = _make_history_df()

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.predicted_monthly_income == pytest.approx(30.0)


def test_confidence_band_width_averages_p90_minus_p10():
    """``confidence_band_width`` = mean(P90 - P10) across horizon."""
    from packages.forecasting.insights import compute_insights

    matrix = np.zeros((3, 7))
    matrix[:, 1] = [10.0, 20.0, 30.0]  # P10
    matrix[:, 5] = [110.0, 120.0, 140.0]  # P90 — diffs 100, 100, 110 → mean 103.33
    matrix[:, 3] = [60.0, 70.0, 80.0]  # P50 anchor
    futures = _future_dates(date(2026, 4, 1), horizon=3)
    history = _make_history_df()

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.confidence_band_width == pytest.approx((100 + 100 + 110) / 3.0)


# ---------------------------------------------------------------------------
# primary_drivers
# ---------------------------------------------------------------------------


def test_primary_drivers_returns_top3_by_weight():
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    futures = _future_dates(date(2026, 4, 1))
    history = _make_history_df()
    vi = {"day_of_week": 0.5, "is_payday": 0.3, "amount_lag1": 0.2, "noise": 0.05}

    out = compute_insights(matrix, futures, history, variable_importance=vi)
    assert len(out.primary_drivers) == 3
    features = [d.feature for d in out.primary_drivers]
    assert features == ["day_of_week", "is_payday", "amount_lag1"]


def test_primary_drivers_empty_for_chronos_only():
    """``variable_importance=None`` → primary_drivers=[]."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    futures = _future_dates(date(2026, 4, 1))
    history = _make_history_df()

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.primary_drivers == []


def test_primary_drivers_empty_for_empty_dict():
    """An empty importance dict (degenerate VSN output) → []."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    futures = _future_dates(date(2026, 4, 1))
    history = _make_history_df()

    out = compute_insights(matrix, futures, history, variable_importance={})
    assert out.primary_drivers == []


# ---------------------------------------------------------------------------
# safe_to_spend / overdraft_risk_score
# ---------------------------------------------------------------------------


def test_safe_to_spend_all_days_above_floor():
    """All P10 above floor → safe_to_spend > 0, overdraft_risk = 0."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    matrix[:, 1] = 10_000.0  # P10 well above any floor
    matrix[:, 3] = 12_000.0
    futures = _future_dates(date(2026, 4, 1))
    history = pd.DataFrame({"closing_balance": [5000.0] * 50})

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.overdraft_risk_score == 0.0
    assert out.safe_to_spend > 0.0


def test_safe_to_spend_zero_when_all_days_below_floor():
    """All P10 below floor → safe_to_spend=0, overdraft_risk=1.0."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    matrix[:, 1] = -1000.0  # P10 always below floor
    futures = _future_dates(date(2026, 4, 1))
    history = pd.DataFrame({"closing_balance": [5000.0] * 50})

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.safe_to_spend == 0.0
    assert out.overdraft_risk_score == 1.0


def test_overdraft_risk_score_is_fraction_of_days_below_floor():
    """``overdraft_risk_score`` = fraction of horizon days where P10 < floor."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix(horizon=10)
    matrix[:, 1] = [100, 100, 100, -100, -100, -100, 100, 100, 100, 100]  # 3/10 below 0
    futures = _future_dates(date(2026, 4, 1), horizon=10)
    history = pd.DataFrame({"closing_balance": [0.0] * 10})  # floor = 0

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.overdraft_risk_score == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_compute_insights_raises_on_missing_closing_balance_column():
    """``history_df`` missing ``closing_balance`` → ValueError."""
    from packages.forecasting.insights import compute_insights

    matrix = _make_forecast_matrix()
    futures = _future_dates(date(2026, 4, 1))
    bad_history = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=5)})

    with pytest.raises(ValueError, match="closing_balance"):
        compute_insights(matrix, futures, bad_history, variable_importance=None)


def test_compute_insights_handles_constant_balance_user():
    """Constant balance (zero deltas) → spend=0, income=0; no divide-by-zero."""
    from packages.forecasting.insights import compute_insights

    matrix = np.zeros((30, 7))
    matrix[:, 3] = 1000.0  # P50 constant
    futures = _future_dates(date(2026, 4, 1))
    history = pd.DataFrame({"closing_balance": [1000.0] * 30})

    out = compute_insights(matrix, futures, history, variable_importance=None)
    assert out.predicted_monthly_spend == 0.0
    assert out.predicted_monthly_income == 0.0
