"""Tests for time-series augmentation helpers (jitter, scale, magnitude_warp)."""

import numpy as np
import pandas as pd

from packages.forecasting.augmentation import jitter, magnitude_warp, scale


def _make_series(n: int = 100) -> pd.Series:
    rng = np.random.default_rng(0)
    return pd.Series(rng.uniform(10, 100, n))


def test_jitter_preserves_shape():
    s = _make_series()
    result = jitter(s, sigma=0.02)
    assert len(result) == len(s)


def test_jitter_adds_noise():
    s = _make_series()
    result = jitter(s, sigma=0.05)
    assert not np.allclose(result.values, s.values)


def test_scale_preserves_shape():
    s = _make_series()
    result = scale(s, low=0.8, high=1.2)
    assert len(result) == len(s)


def test_scale_changes_magnitude():
    s = pd.Series([100.0] * 50)
    # low == high collapses the uniform draw to a deterministic factor.
    result = scale(s, low=0.5, high=0.5)
    assert np.allclose(result.values, 50.0)


def test_magnitude_warp_preserves_shape():
    s = _make_series()
    result = magnitude_warp(s, sigma=0.1, knots=4)
    assert len(result) == len(s)


def test_magnitude_warp_is_smooth():
    """Warped series should not exhibit large jumps relative to a flat input."""
    s = pd.Series([100.0] * 100)
    result = magnitude_warp(s, sigma=0.1, knots=4)
    diffs = np.abs(np.diff(result.values))
    assert np.max(diffs) < 20, "magnitude warp should produce smooth changes"
