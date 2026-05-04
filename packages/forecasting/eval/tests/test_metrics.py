"""Tests for RFC-006 §5 evaluation metrics.

Golden tests cross-check the local pinball-loss implementation against
``sklearn.metrics.mean_pinball_loss`` to within 1e-9 across all 7 quantile
levels (per RFC-006 §"Success Metrics").
"""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import mean_pinball_loss as sk_mean_pinball_loss

from packages.forecasting.eval.metrics import (
    QUANTILE_LEVELS,
    coverage,
    interval_width,
    mape,
    mean_pinball_loss,
    pinball_loss,
    pinball_loss_all_quantiles,
)

# ---------------------------------------------------------------------------
# pinball golden tests vs sklearn
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tau", [0.10, 0.50, 0.90])
def test_pinball_matches_sklearn_three_quantiles(tau: float) -> None:
    """RFC-006 §"Success Metrics": pinball delta vs sklearn ≤ 1e-9 across
    quantile levels. Spot-check 3 representative levels."""
    rng = np.random.default_rng(seed=42)
    actual = rng.normal(loc=100.0, scale=10.0, size=200)
    pred = actual + rng.normal(loc=0.0, scale=2.0, size=200)

    ours = pinball_loss(pred, actual, tau)
    theirs = sk_mean_pinball_loss(actual, pred, alpha=tau)

    assert abs(ours - theirs) < 1e-9, f"pinball_loss(tau={tau}) diverges from sklearn: ours={ours}, sk={theirs}"


@pytest.mark.parametrize("tau", list(QUANTILE_LEVELS))
def test_pinball_matches_sklearn_all_seven_quantiles(tau: float) -> None:
    """All seven RFC-003 quantile levels match sklearn within tolerance."""
    rng = np.random.default_rng(seed=7)
    actual = rng.uniform(50.0, 500.0, size=120)
    pred = actual + rng.normal(loc=5.0, scale=8.0, size=120)

    ours = pinball_loss(pred, actual, tau)
    theirs = sk_mean_pinball_loss(actual, pred, alpha=tau)

    assert abs(ours - theirs) < 1e-9


def test_pinball_loss_all_quantiles_returns_dict_keyed_by_tau() -> None:
    rng = np.random.default_rng(seed=0)
    horizon = 30
    actual = rng.normal(loc=1000.0, scale=100.0, size=horizon)
    forecast = np.stack([actual + (q - 0.5) * 50.0 for q in QUANTILE_LEVELS], axis=1)
    assert forecast.shape == (horizon, 7)

    losses = pinball_loss_all_quantiles(forecast, actual)
    assert set(losses.keys()) == set(QUANTILE_LEVELS)
    for tau, loss in losses.items():
        assert loss >= 0.0
        # Cross-check vs sklearn at the median to anchor the dict.
        sk = sk_mean_pinball_loss(actual, forecast[:, QUANTILE_LEVELS.index(tau)], alpha=tau)
        assert abs(loss - sk) < 1e-9


def test_mean_pinball_loss_matrix_form() -> None:
    """Top-level ``mean_pinball_loss`` accepts (horizon, n_quantiles) and
    returns the mean loss across quantile levels (averaged over time + tau)."""
    rng = np.random.default_rng(seed=1)
    horizon = 30
    actual = rng.normal(loc=500.0, scale=50.0, size=horizon)
    forecast = np.stack([actual + (q - 0.5) * 30.0 for q in QUANTILE_LEVELS], axis=1)
    out = mean_pinball_loss(actual, forecast, QUANTILE_LEVELS)

    expected = np.mean([sk_mean_pinball_loss(actual, forecast[:, i], alpha=q) for i, q in enumerate(QUANTILE_LEVELS)])
    assert abs(out - expected) < 1e-9


# ---------------------------------------------------------------------------
# MAPE
# ---------------------------------------------------------------------------


def test_mape_zero_when_perfect() -> None:
    actual = np.array([100.0, 200.0, 300.0])
    pred = actual.copy()
    assert mape(pred, actual) == 0.0


def test_mape_known_value() -> None:
    actual = np.array([100.0, 100.0, 100.0])
    pred = np.array([110.0, 90.0, 100.0])
    # |110-100|/100 + |90-100|/100 + 0 / 3 = (0.1 + 0.1 + 0)/3 = 0.066...
    assert abs(mape(pred, actual) - (0.2 / 3.0)) < 1e-12


def test_mape_clamps_low_denominator() -> None:
    """Denominator is clamped to 1.0 to prevent blowup near zero."""
    actual = np.array([0.0, 0.0])
    pred = np.array([5.0, 10.0])
    # With clamp at 1.0: |5-0|/1.0 + |10-0|/1.0 / 2 = 7.5
    assert mape(pred, actual) == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# Coverage + interval width
# ---------------------------------------------------------------------------


def test_coverage_full_band() -> None:
    actual = np.array([10.0, 20.0, 30.0])
    lower = np.array([0.0, 0.0, 0.0])
    upper = np.array([100.0, 100.0, 100.0])
    assert coverage(actual, lower, upper) == 1.0


def test_coverage_no_band() -> None:
    actual = np.array([10.0, 20.0, 30.0])
    lower = np.array([100.0, 100.0, 100.0])
    upper = np.array([200.0, 200.0, 200.0])
    assert coverage(actual, lower, upper) == 0.0


def test_coverage_partial_band() -> None:
    actual = np.array([5.0, 50.0, 95.0])
    lower = np.array([0.0, 0.0, 0.0])
    upper = np.array([10.0, 10.0, 100.0])
    # actual[0]=5 in [0,10] yes; actual[1]=50 not in [0,10]; actual[2]=95 in [0,100]
    assert coverage(actual, lower, upper) == pytest.approx(2.0 / 3.0)


def test_interval_width_simple() -> None:
    lower = np.array([0.0, 10.0, 20.0])
    upper = np.array([10.0, 30.0, 60.0])
    # widths = 10, 20, 40 → mean 23.33
    assert interval_width(lower, upper) == pytest.approx((10 + 20 + 40) / 3.0)
