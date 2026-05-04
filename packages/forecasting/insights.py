"""Server-side forecast insights — RFC-003 §2 pure-function compute layer.

Inputs: a 7-quantile forecast matrix (shape ``(horizon, 7)`` —
``[p2, p10, p25, p50, p75, p90, p98]``), the future date list, the
user's history ``DataFrame`` (for floor derivation), and an optional
variable-importance dict from the TFT VSN.

Outputs: a fully-populated :class:`ForecastInsights` Pydantic model.

No DB. No HTTP. No logging side effects. The ``ForecastService`` wraps
this module's ``compute_insights`` in a guarded block and falls back to
:func:`_safe_default_insights` on any exception so the caller never
fails with a 500 when an insights-math edge case slips through.

RFC-005 Layer 4 integration: ``compute_insights`` calls
:func:`packages.forecasting.stochastic_widener.widen_intervals` on the
forecast matrix BEFORE deriving any insights. ``active_intents=None`` in
v1; Stage 6 wires user-intent feeding.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §2
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd

from apps.api.domains.forecasting.schemas import (
    ForecastInsights,
    LowestBalance,
    QuantileSnapshot,
    VariableImportance,
)
from packages.forecasting.stochastic_widener import widen_intervals

logger = logging.getLogger(__name__)

# Bumped whenever ``compute_insights`` math changes in a way that could
# alter persisted ForecastInsights values. Stage 5 = "v1".
INSIGHTS_VERSION: str = "v1"


# ---------------------------------------------------------------------------
# derive_floor
# ---------------------------------------------------------------------------


def derive_floor(
    history_df: pd.DataFrame,
    user_override: float | None = None,
) -> tuple[float, str]:
    """Return ``(floor_value, floor_source)``.

    * ``user_override`` supplied → ``(float(user_override), "user_override")``
    * Else → ``(max(0.0, P10(history.closing_balance)), "auto_p10_history")``

    The clamp at zero matches the RFC-003 §2 spec: a user whose
    historical P10 balance is negative (always-overdrawn account) gets a
    floor of zero rather than a negative bar that would render
    ``safe_to_spend`` always positive.

    Raises:
        ValueError: If ``history_df`` lacks a ``closing_balance`` column.
    """
    if user_override is not None:
        return float(user_override), "user_override"

    if "closing_balance" not in history_df.columns:
        raise ValueError("cannot derive floor without closing_balance history")

    balance = pd.to_numeric(history_df["closing_balance"], errors="coerce").dropna()
    if balance.empty:
        return 0.0, "auto_p10_history"

    p10 = float(balance.quantile(0.10))
    return max(0.0, round(p10, 2)), "auto_p10_history"


# ---------------------------------------------------------------------------
# compute_insights
# ---------------------------------------------------------------------------


def compute_insights(
    forecast_matrix: np.ndarray,
    future_dates: list[date] | list[pd.Timestamp],
    history_df: pd.DataFrame,
    variable_importance: dict[str, float] | None = None,
    user_floor_override: float | None = None,
    active_intents: Iterable[object] | None = None,
) -> ForecastInsights:
    """Derive a :class:`ForecastInsights` from a forecast matrix.

    Args:
        forecast_matrix: ``(horizon, 7)`` ndarray of quantiles in order
            ``[p2, p10, p25, p50, p75, p90, p98]``.
        future_dates: Length-``horizon`` list of dates (one per matrix
            row). Used to populate the date in
            :class:`LowestBalance`.
        history_df: User's history. Must carry a ``closing_balance``
            column for floor derivation.
        variable_importance: Optional ``{feature: weight}`` dict from
            the TFT VSN. ``None`` for Chronos-only forecasts (which
            have no VSN output) or when the model doesn't expose one.
        user_floor_override: Optional v1.5 ``user_profile.balance_floor``
            value. ``None`` in v1.
        active_intents: Optional iterable of user intents (Stage 6).
            ``None`` in v1; passes straight through to
            :func:`widen_intervals`.

    Returns:
        Populated :class:`ForecastInsights`.

    Raises:
        ValueError: If ``history_df`` lacks ``closing_balance`` (raised
            by :func:`derive_floor`).
    """
    matrix = np.asarray(forecast_matrix, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != 7:
        raise ValueError(f"forecast_matrix must be (horizon, 7); got shape {matrix.shape}")

    # RFC-005 Layer 4 — widen intervals BEFORE deriving insights so that
    # safe_to_spend / overdraft_risk_score reflect the inflated bands.
    matrix = widen_intervals(matrix, volatilities=None, active_intents=active_intents)

    horizon = matrix.shape[0]

    # Quantile column indices.
    P2, P10, P25, P50, P75, P90, P98 = 0, 1, 2, 3, 4, 5, 6

    # ------------------------------------------------------------------ #
    # Floor (may raise if history malformed).
    # ------------------------------------------------------------------ #
    floor_used, floor_source = derive_floor(history_df, user_override=user_floor_override)

    # ------------------------------------------------------------------ #
    # lowest_balance — day where P10 is minimised.
    # ------------------------------------------------------------------ #
    p10_col = matrix[:, P10]
    p50_col = matrix[:, P50]
    min_idx = int(np.argmin(p10_col))
    min_date_obj = future_dates[min_idx]
    if hasattr(min_date_obj, "strftime"):
        min_date_str = min_date_obj.strftime("%Y-%m-%d")
    else:
        min_date_str = str(min_date_obj)
    lowest_balance = LowestBalance(
        date=min_date_str,
        p10=float(p10_col[min_idx]),
        p50=float(p50_col[min_idx]),
    )

    # ------------------------------------------------------------------ #
    # month_end — last day of horizon (rolling, not calendar).
    # ------------------------------------------------------------------ #
    month_end = QuantileSnapshot(
        p10=float(matrix[-1, P10]),
        p50=float(matrix[-1, P50]),
        p90=float(matrix[-1, P90]),
    )

    # ------------------------------------------------------------------ #
    # predicted_monthly_spend / income — sum of signed P50 deltas.
    # ------------------------------------------------------------------ #
    if horizon < 2:
        predicted_monthly_spend = 0.0
        predicted_monthly_income = 0.0
    else:
        try:
            deltas = np.diff(p50_col)
            negative = deltas[deltas < 0]
            positive = deltas[deltas > 0]
            predicted_monthly_spend = float(round(np.abs(negative.sum()), 2)) if negative.size else 0.0
            predicted_monthly_income = float(round(positive.sum(), 2)) if positive.size else 0.0
        except ZeroDivisionError:
            logger.info("monthly_aggregation_divide_by_zero")
            predicted_monthly_spend = 0.0
            predicted_monthly_income = 0.0

    # ------------------------------------------------------------------ #
    # confidence_band_width — mean(P90 - P10).
    # ------------------------------------------------------------------ #
    band = matrix[:, P90] - matrix[:, P10]
    confidence_band_width = float(round(band.mean(), 4)) if band.size else 0.0

    # ------------------------------------------------------------------ #
    # primary_drivers — top 3 (feature, weight) by weight desc.
    # ------------------------------------------------------------------ #
    if variable_importance:
        sorted_drivers = sorted(variable_importance.items(), key=lambda kv: float(kv[1]), reverse=True)[:3]
        primary_drivers = [VariableImportance(feature=f, weight=float(w)) for f, w in sorted_drivers]
    else:
        primary_drivers = []

    # ------------------------------------------------------------------ #
    # safe_to_spend / overdraft_risk_score.
    # ------------------------------------------------------------------ #
    below_floor_mask = p10_col < floor_used
    overdraft_risk_score = float(below_floor_mask.sum()) / horizon if horizon else 0.0
    overdraft_risk_score = round(overdraft_risk_score, 4)

    if overdraft_risk_score >= 1.0 - 1e-9:
        safe_to_spend = 0.0
    else:
        # Largest one-shot spend such that every horizon day's P10 stays
        # at or above the floor. The minimum slack across horizon days
        # is the binding constraint.
        slack = float(np.min(p10_col) - floor_used)
        safe_to_spend = max(0.0, round(slack, 2))

    return ForecastInsights(
        lowest_balance=lowest_balance,
        month_end=month_end,
        predicted_monthly_spend=predicted_monthly_spend,
        predicted_monthly_income=predicted_monthly_income,
        confidence_band_width=confidence_band_width,
        primary_drivers=primary_drivers,
        safe_to_spend=safe_to_spend,
        overdraft_risk_score=float(overdraft_risk_score),
        floor_used=float(floor_used),
        floor_source=floor_source,
    )


# ---------------------------------------------------------------------------
# _safe_default_insights — fallback when compute_insights raises.
# ---------------------------------------------------------------------------


def _safe_default_insights(raw: object | None = None) -> ForecastInsights:
    """Zero-filled fallback :class:`ForecastInsights`.

    Used by :class:`ForecastService` when :func:`compute_insights`
    raises — degraded insights + a structlog warn beats a 500 to the
    user. ``floor_source`` defaults to ``"auto_p10_history"`` because
    the user-override slot is reserved for v1.5.

    The ``raw`` parameter is reserved for future extension (e.g.
    populating ``month_end`` from the actual forecast even when other
    derivations failed); v1 ignores it.
    """
    return ForecastInsights(
        lowest_balance=LowestBalance(date="1970-01-01", p10=0.0, p50=0.0),
        month_end=QuantileSnapshot(p10=0.0, p50=0.0, p90=0.0),
        predicted_monthly_spend=0.0,
        predicted_monthly_income=0.0,
        confidence_band_width=0.0,
        primary_drivers=[],
        safe_to_spend=0.0,
        overdraft_risk_score=0.0,
        floor_used=0.0,
        floor_source="auto_p10_history",
    )


__all__ = [
    "INSIGHTS_VERSION",
    "compute_insights",
    "derive_floor",
    "_safe_default_insights",
]
