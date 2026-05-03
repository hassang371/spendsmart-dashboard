"""Tests for RFC-005 Layer 4 — stochastic widener."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from packages.forecasting.stochastic_widener import (
    MAX_SPREAD_MULTIPLIER,
    SPREAD_BUMP_INTENT,
    SPREAD_BUMP_VOLATILITY,
    VOLATILITY_THRESHOLD_CV,
    compute_bucket_volatility,
    widen_intervals,
)


def _sample_forecast(horizon: int = 5) -> np.ndarray:
    """Symmetric quantile matrix around P50=100. Distances from median:
    [-50, -30, -10, 0, +10, +30, +50] for [P02, P10, P25, P50, P75, P90, P98].
    """
    spreads = np.array([-50.0, -30.0, -10.0, 0.0, 10.0, 30.0, 50.0])
    return np.tile(spreads + 100.0, (horizon, 1))


def test_widen_passthrough_when_no_bumps():
    forecast = _sample_forecast()
    out = widen_intervals(forecast, volatilities={"groceries": 0.5}, active_intents=())
    np.testing.assert_array_equal(out, forecast)


def test_widen_volatility_bump_inflates_outer_quantiles():
    forecast = _sample_forecast()
    high_vol = {"transport": VOLATILITY_THRESHOLD_CV + 0.1}
    out = widen_intervals(forecast, volatilities=high_vol)

    # P50 unchanged
    assert (out[:, 3] == forecast[:, 3]).all()
    # P10 spread inflated by SPREAD_BUMP_VOLATILITY
    expected_p10_spread = -30.0 * (1.0 + SPREAD_BUMP_VOLATILITY)
    np.testing.assert_allclose(out[:, 1] - 100.0, expected_p10_spread)
    # P02 likewise
    expected_p02_spread = -50.0 * (1.0 + SPREAD_BUMP_VOLATILITY)
    np.testing.assert_allclose(out[:, 0] - 100.0, expected_p02_spread)


def test_widen_intent_bump_triggered_by_life_event():
    forecast = _sample_forecast()
    intents = [{"intent_type": "LIFE_EVENT", "confidence": "high"}]
    out = widen_intervals(forecast, volatilities=None, active_intents=intents)

    expected_p90_spread = 30.0 * (1.0 + SPREAD_BUMP_INTENT)
    np.testing.assert_allclose(out[:, 5] - 100.0, expected_p90_spread)


def test_widen_volatility_and_intent_stack():
    forecast = _sample_forecast()
    high_vol = {"transport": VOLATILITY_THRESHOLD_CV + 0.1}
    intents = [{"intent_type": "LIFE_EVENT"}]
    out = widen_intervals(forecast, volatilities=high_vol, active_intents=intents)

    expected_multiplier = 1.0 + SPREAD_BUMP_VOLATILITY + SPREAD_BUMP_INTENT
    expected_multiplier = min(expected_multiplier, MAX_SPREAD_MULTIPLIER)
    expected_p90_spread = 30.0 * expected_multiplier
    np.testing.assert_allclose(out[:, 5] - 100.0, expected_p90_spread)


def test_widen_caps_at_max_multiplier():
    forecast = _sample_forecast()
    # Construct stacked bumps that exceed the cap.
    huge_intents = [{"intent_type": "LIFE_EVENT"}, {"intent_type": "LIFE_EVENT"}]
    high_vol = {"x": VOLATILITY_THRESHOLD_CV + 5.0}
    out = widen_intervals(forecast, volatilities=high_vol, active_intents=huge_intents)
    # Even multiple LIFE_EVENT entries only fire SPREAD_BUMP_INTENT once
    # per the rule (any LIFE_EVENT triggers the bump). The cap is the
    # ultimate guard.
    expected_multiplier = min(
        1.0 + SPREAD_BUMP_VOLATILITY + SPREAD_BUMP_INTENT,
        MAX_SPREAD_MULTIPLIER,
    )
    np.testing.assert_allclose(out[:, 5] - 100.0, 30.0 * expected_multiplier)


def test_widen_inner_quantiles_widen_at_half_rate():
    forecast = _sample_forecast()
    high_vol = {"x": VOLATILITY_THRESHOLD_CV + 1.0}
    out = widen_intervals(forecast, volatilities=high_vol)

    # P25/P75 widen by half the multiplier delta.
    inner_scale = 1.0 + (SPREAD_BUMP_VOLATILITY) * 0.5
    np.testing.assert_allclose(out[:, 4] - 100.0, 10.0 * inner_scale)
    np.testing.assert_allclose(out[:, 2] - 100.0, -10.0 * inner_scale)


def test_widen_rejects_wrong_shape():
    bad = np.zeros((5, 3))
    with pytest.raises(ValueError):
        widen_intervals(bad)


# ---------------------------------------------------------------------------
# compute_bucket_volatility
# ---------------------------------------------------------------------------


def _build_panel(buckets: dict[str, list[float]]) -> pd.DataFrame:
    """Build a panel where each bucket's bucket_total series is the
    list of values supplied (one per consecutive day)."""
    n = max(len(values) for values in buckets.values())
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    rows = []
    for bucket, values in buckets.items():
        for i, d in enumerate(dates):
            rows.append(
                {
                    "date": d,
                    "category_bucket": bucket,
                    "bucket_total": values[i] if i < len(values) else 0.0,
                }
            )
    return pd.DataFrame(rows)


def test_volatility_returns_per_bucket_cv():
    panel = _build_panel(
        {
            "groceries": [100.0, 100.0, 100.0, 100.0],  # zero std → cv 0
            "dining": [50.0, 200.0, 50.0, 200.0],  # high cv
        }
    )
    vols = compute_bucket_volatility(panel)
    assert vols["groceries"] == pytest.approx(0.0, abs=1e-9)
    assert vols["dining"] > 0.0


def test_volatility_noise_floor_zero_when_mean_below_one():
    panel = _build_panel({"transfer": [0.1, -0.1, 0.0]})
    vols = compute_bucket_volatility(panel)
    assert vols["transfer"] == 0.0


def test_volatility_handles_empty_panel():
    assert compute_bucket_volatility(pd.DataFrame()) == {}


def test_volatility_uses_last_90_days_window():
    """Older data outside the 90-day window is ignored."""
    dates_old = pd.date_range("2025-01-01", periods=10, freq="D")
    dates_recent = pd.date_range("2026-01-01", periods=10, freq="D")
    rows = []
    for d in dates_old:
        rows.append({"date": d, "category_bucket": "x", "bucket_total": 1000.0})
    for d in dates_recent:
        rows.append({"date": d, "category_bucket": "x", "bucket_total": 50.0})
    panel = pd.DataFrame(rows)

    vols = compute_bucket_volatility(panel)
    # Only recent values should contribute; their std is 0 → cv 0.
    assert vols["x"] == pytest.approx(0.0, abs=1e-9)
