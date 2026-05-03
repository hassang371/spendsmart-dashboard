"""Time-series data augmentation for financial forecasting.

All helpers take a ``pd.Series`` and return a ``pd.Series`` of the same
length. Temporal order is always preserved — the augmentation operates
in-place on the value axis only.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.interpolate import CubicSpline


def jitter(series: pd.Series, sigma: float = 0.02) -> pd.Series:
    """Add Gaussian noise scaled to the series standard deviation.

    Args:
        series: Input series.
        sigma: Noise scale, expressed as a fraction of the input std.
    """
    noise = np.random.normal(0, sigma * series.std(), size=len(series))
    return pd.Series(series.values + noise, index=series.index)


def scale(series: pd.Series, low: float = 0.8, high: float = 1.2) -> pd.Series:
    """Multiply the entire series by a single random factor in ``[low, high]``."""
    factor = np.random.uniform(low, high)
    return pd.Series(series.values * factor, index=series.index)


def magnitude_warp(
    series: pd.Series,
    sigma: float = 0.1,
    knots: int = 4,
) -> pd.Series:
    """Multiply by a smooth cubic-spline curve to vary magnitude over time.

    Args:
        series: Input series.
        sigma: Std-dev of the random per-knot multiplier (mean 1.0).
        knots: Number of interior knots to draw before fitting the spline.
    """
    n = len(series)
    knot_positions = np.linspace(0, n - 1, knots + 2)
    knot_values = np.random.normal(1.0, sigma, size=knots + 2)
    spline = CubicSpline(knot_positions, knot_values)
    warp_curve = spline(np.arange(n))
    return pd.Series(series.values * warp_curve, index=series.index)
