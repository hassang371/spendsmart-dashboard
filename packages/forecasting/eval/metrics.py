"""RFC-006 §5 — evaluation metrics for the walk-forward harness.

All functions are pure NumPy. Pinball loss is golden-tested against
``sklearn.metrics.mean_pinball_loss`` to within 1e-9 (see
``tests/test_metrics.py``).

The quantile set mirrors RFC-003 §1 ``ForecastPoint`` schema and the
``user_predictions.pinball_loss`` jsonb keys ``{p2, p10, p25, p50, p75, p90,
p98}``. Any future change to the quantile set must land in RFC-003 first;
this module mirrors the RFC-003 contract.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

# Source of truth: RFC-003 §1 ForecastPoint schema.
QUANTILE_LEVELS: tuple[float, ...] = (0.02, 0.10, 0.25, 0.50, 0.75, 0.90, 0.98)


# ---------------------------------------------------------------------------
# Pinball loss
# ---------------------------------------------------------------------------


def pinball_loss(
    y_pred: np.ndarray | Sequence[float],
    y_true: np.ndarray | Sequence[float],
    tau: float,
) -> float:
    """Pinball loss at quantile ``tau``.

    Formula (matches ``sklearn.metrics.mean_pinball_loss``):

        L_tau(y, q) = mean( max(tau * (y - q), (tau - 1) * (y - q)) )

    Args:
        y_pred: Quantile forecast at level ``tau``, shape (horizon,).
        y_true: Actual values, shape (horizon,).
        tau:    Quantile level in (0, 1).

    Returns:
        Mean pinball loss (scalar, ≥ 0).
    """
    y_pred = np.asarray(y_pred, dtype=float)
    y_true = np.asarray(y_true, dtype=float)
    if y_pred.shape != y_true.shape:
        raise ValueError(f"pinball_loss shape mismatch: y_pred={y_pred.shape}, y_true={y_true.shape}")
    diff = y_true - y_pred
    loss = np.maximum(tau * diff, (tau - 1.0) * diff)
    return float(loss.mean())


def pinball_loss_all_quantiles(
    forecast_matrix: np.ndarray,
    y_true: np.ndarray | Sequence[float],
    quantile_levels: Sequence[float] = QUANTILE_LEVELS,
) -> dict[float, float]:
    """Per-quantile pinball loss.

    Args:
        forecast_matrix: Shape (horizon, n_quantiles); columns ordered to
            match ``quantile_levels``.
        y_true:          Shape (horizon,).
        quantile_levels: Tuple of taus (default RFC-003 7-quantile set).

    Returns:
        ``{tau: loss}`` for each quantile level.
    """
    forecast_matrix = np.asarray(forecast_matrix, dtype=float)
    y_true = np.asarray(y_true, dtype=float)
    if forecast_matrix.ndim != 2:
        raise ValueError(f"forecast_matrix must be 2D (horizon, n_quantiles); got shape {forecast_matrix.shape}")
    if forecast_matrix.shape[1] != len(quantile_levels):
        raise ValueError(
            f"forecast_matrix columns ({forecast_matrix.shape[1]}) must equal "
            f"len(quantile_levels) ({len(quantile_levels)})"
        )
    return {float(tau): pinball_loss(forecast_matrix[:, idx], y_true, tau) for idx, tau in enumerate(quantile_levels)}


def mean_pinball_loss(
    y_true: np.ndarray | Sequence[float],
    y_pred_quantiles: np.ndarray,
    quantile_levels: Sequence[float] = QUANTILE_LEVELS,
) -> float:
    """Mean pinball loss across all quantile levels.

    Convenience wrapper for the headline summary stat used in RFC-006 §7
    reports ("Pinball loss (mean 7q)").

    Args:
        y_true:           Shape (horizon,).
        y_pred_quantiles: Shape (horizon, n_quantiles), columns aligned to
            ``quantile_levels``.
        quantile_levels:  Tuple of taus.

    Returns:
        Scalar mean pinball loss across all quantiles + horizon points.
    """
    per_q = pinball_loss_all_quantiles(y_pred_quantiles, y_true, quantile_levels)
    return float(np.mean(list(per_q.values())))


# ---------------------------------------------------------------------------
# MAPE on the P50 median
# ---------------------------------------------------------------------------


def mape(
    y_pred: np.ndarray | Sequence[float],
    y_true: np.ndarray | Sequence[float],
    *,
    denominator_floor: float = 1.0,
) -> float:
    """Mean absolute percentage error on the P50 median.

    Denominator is clamped to ``denominator_floor`` (default 1.0 INR) to
    prevent division-by-near-zero blowing up on low-balance days.

    Args:
        y_pred:            P50 forecast, shape (horizon,).
        y_true:            Actuals, shape (horizon,).
        denominator_floor: Lower bound on |y_true|. Default 1.0.

    Returns:
        Scalar MAPE (e.g. 0.10 = 10%).
    """
    y_pred = np.asarray(y_pred, dtype=float)
    y_true = np.asarray(y_true, dtype=float)
    if y_pred.shape != y_true.shape:
        raise ValueError(f"mape shape mismatch: y_pred={y_pred.shape}, y_true={y_true.shape}")
    denom = np.maximum(np.abs(y_true), denominator_floor)
    return float(np.mean(np.abs(y_pred - y_true) / denom))


# ---------------------------------------------------------------------------
# Interval coverage + width
# ---------------------------------------------------------------------------


def coverage(
    y_true: np.ndarray | Sequence[float],
    y_pred_lower: np.ndarray | Sequence[float],
    y_pred_upper: np.ndarray | Sequence[float],
) -> float:
    """Fraction of actual values inside ``[lower, upper]`` (inclusive).

    Used for P10–P90 coverage assessment per RFC-006 §"Detailed Design 5"
    (target ≥ 0.80).
    """
    y_true = np.asarray(y_true, dtype=float)
    lower = np.asarray(y_pred_lower, dtype=float)
    upper = np.asarray(y_pred_upper, dtype=float)
    if not (y_true.shape == lower.shape == upper.shape):
        raise ValueError(
            f"coverage shape mismatch: y_true={y_true.shape}, " f"lower={lower.shape}, upper={upper.shape}"
        )
    inside = (y_true >= lower) & (y_true <= upper)
    return float(inside.mean())


def interval_width(
    y_pred_lower: np.ndarray | Sequence[float],
    y_pred_upper: np.ndarray | Sequence[float],
) -> float:
    """Mean width of the ``[lower, upper]`` interval across the horizon."""
    lower = np.asarray(y_pred_lower, dtype=float)
    upper = np.asarray(y_pred_upper, dtype=float)
    if lower.shape != upper.shape:
        raise ValueError(f"interval_width shape mismatch: lower={lower.shape}, upper={upper.shape}")
    return float(np.mean(upper - lower))


# ---------------------------------------------------------------------------
# Calibration error
# ---------------------------------------------------------------------------


def calibration_error(
    forecast_matrix: np.ndarray,
    y_true: np.ndarray | Sequence[float],
    quantile_levels: Sequence[float] = QUANTILE_LEVELS,
) -> dict[str, object]:
    """Per-quantile calibration error.

    For each tau, compute the observed fraction of actuals ≤ forecast[tau]
    and the absolute deviation from tau. Mean |observed - tau| is the
    headline calibration error (RFC-006 threshold ≤ 0.05).
    """
    forecast_matrix = np.asarray(forecast_matrix, dtype=float)
    y_true = np.asarray(y_true, dtype=float)
    observed: dict[float, float] = {}
    deviation: dict[float, float] = {}
    for idx, tau in enumerate(quantile_levels):
        frac = float((y_true <= forecast_matrix[:, idx]).mean())
        observed[float(tau)] = frac
        deviation[float(tau)] = abs(frac - float(tau))
    return {
        "observed": observed,
        "deviation": deviation,
        "mean_abs_deviation": float(np.mean(list(deviation.values()))),
    }
