"""Tests for the TFT + Chronos-2 weighted-ensemble blender.

Override per RFC-003 §1: blends across all seven RFC-003 quantiles
(p2, p10, p25, p50, p75, p90, p98), not the historical 3-quantile
shape.
"""

import pytest

from packages.forecasting.ensemble import ensemble_forecasts

QUANTILE_KEYS = ("p2", "p10", "p25", "p50", "p75", "p90", "p98")


def _make_forecast(offset: float = 0.0, *, horizon: int = 2) -> dict:
    points = []
    for i in range(horizon):
        date = f"2026-04-{7 + i:02d}"
        # Each quantile is offset by a known increment so the ordering test
        # has something meaningful to verify.
        point = {"date": date}
        for q_idx, key in enumerate(QUANTILE_KEYS):
            point[key] = 100.0 + 10.0 * q_idx + offset + i
        points.append(point)
    return {
        "forecast": points,
        "model_type": "test",
        "model_version": "v1",
        "horizon": horizon,
    }


def test_ensemble_blends_all_seven_quantiles_at_configured_weights():
    """0.7 * tft + 0.3 * chronos applied to every RFC-003 quantile key."""
    tft = _make_forecast(0.0)
    chronos = _make_forecast(100.0)

    result = ensemble_forecasts(tft, chronos, tft_weight=0.7, chronos_weight=0.3)

    assert result["model_type"] == "ensemble"
    for i, point in enumerate(result["forecast"]):
        for q_idx, key in enumerate(QUANTILE_KEYS):
            tft_v = 100.0 + 10.0 * q_idx + 0.0 + i
            chr_v = 100.0 + 10.0 * q_idx + 100.0 + i
            expected = 0.7 * tft_v + 0.3 * chr_v
            assert point[key] == pytest.approx(
                expected, abs=0.01
            ), f"blend mismatch at point {i} key {key}: got {point[key]}"


def test_ensemble_handles_missing_tft():
    """When TFT is unavailable, return Chronos forecast unchanged."""
    chronos = _make_forecast(100.0)
    result = ensemble_forecasts(None, chronos, tft_weight=0.7, chronos_weight=0.3)

    assert result["model_type"] == chronos["model_type"]
    assert result["forecast"] == chronos["forecast"]


def test_ensemble_requires_matching_horizons():
    """Mismatched horizons should raise ValueError."""
    tft = _make_forecast(horizon=2)
    chronos = _make_forecast(horizon=1)

    with pytest.raises(ValueError, match="horizon"):
        ensemble_forecasts(tft, chronos)


def test_ensemble_preserves_quantile_ordering():
    """If both inputs are quantile-ordered, the blend must be too."""
    # Build inputs whose quantiles are strictly ordered.
    tft = _make_forecast(0.0)
    chronos = _make_forecast(0.0)

    result = ensemble_forecasts(tft, chronos, tft_weight=0.5, chronos_weight=0.5)

    for point in result["forecast"]:
        values = [point[k] for k in QUANTILE_KEYS]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1] + 1e-9, f"blend broke ordering at {point['date']}: {values}"
