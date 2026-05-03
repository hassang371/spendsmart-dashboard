"""RFC-005 Layer 4 — rule-based prediction-interval widening.

No ML. Pure math. Runs inside ``compute_insights`` (RFC-003 §3) after
ensemble blending and before ``ForecastInsights`` assembly.

The widener inflates the spread of the 7 quantiles around the P50
median based on:
    1. Per-bucket coefficient-of-variation (CV) measured on the last 90
       days of bucket totals. CV > ``VOLATILITY_THRESHOLD_CV`` (default
       1.5) triggers a ``SPREAD_BUMP_VOLATILITY`` (+15%) widening.
    2. Active LIFE_EVENT user intents (LLD 010) — when present, applies
       an additional ``SPREAD_BUMP_INTENT`` (+25%) widening; low/medium
       confidence intents stack on top of LIFE_EVENT.

The total spread multiplier is capped at ``MAX_SPREAD_MULTIPLIER``
(default 2.0). The P50 median is never shifted; only interval width
changes.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

VOLATILITY_THRESHOLD_CV: float = 1.5
SPREAD_BUMP_VOLATILITY: float = 0.15  # +15% per RFC-005 §Layer 4
SPREAD_BUMP_INTENT: float = 0.25  # +25% on active LIFE_EVENT
MAX_SPREAD_MULTIPLIER: float = 2.0
NOISE_FLOOR_INR: float = 1.0

__all__ = [
    "VOLATILITY_THRESHOLD_CV",
    "SPREAD_BUMP_VOLATILITY",
    "SPREAD_BUMP_INTENT",
    "MAX_SPREAD_MULTIPLIER",
    "compute_bucket_volatility",
    "widen_intervals",
]


def compute_bucket_volatility(history_panel: pd.DataFrame) -> dict[str, float]:
    """Per-bucket coefficient of variation over the last 90 days.

    ``cv = std(bucket_total) / abs(mean(bucket_total))``. Buckets whose
    absolute mean is below ``NOISE_FLOOR_INR`` are treated as ``cv=0``
    (noise floor — avoids tiny-mean buckets producing huge CV values).

    Args:
        history_panel: Panel DataFrame with ``date``, ``category_bucket``,
            and ``bucket_total`` columns. The function selects the last
            90 days of dates from the panel; if the panel has fewer than
            90 distinct dates, all rows are used.

    Returns:
        Dict mapping ``category_bucket`` → CV (non-negative float).
        Buckets absent from the panel are absent from the dict.
    """
    if history_panel is None or len(history_panel) == 0:
        return {}
    if "category_bucket" not in history_panel.columns:
        return {}
    if "bucket_total" not in history_panel.columns:
        return {}
    if "date" not in history_panel.columns:
        return {}

    panel = history_panel.copy()
    panel["date"] = pd.to_datetime(panel["date"])
    last_date = panel["date"].max()
    cutoff = last_date - pd.Timedelta(days=90)
    recent = panel[panel["date"] >= cutoff]
    if recent.empty:
        recent = panel

    out: dict[str, float] = {}
    for bucket, group in recent.groupby("category_bucket"):
        values = pd.to_numeric(group["bucket_total"], errors="coerce").fillna(0.0).to_numpy()
        if values.size == 0:
            out[str(bucket)] = 0.0
            continue
        mean_abs = float(np.abs(np.mean(values)))
        if mean_abs <= NOISE_FLOOR_INR:
            out[str(bucket)] = 0.0
            continue
        std = float(np.std(values))
        out[str(bucket)] = std / mean_abs
    return out


def _intent_is_life_event(intent: object) -> bool:
    """True when the intent's type is the LIFE_EVENT category.

    Tolerates several shapes:
        - ``IntentType`` enum (Stage 6) with ``.name == "LIFE_EVENT"``
        - Pydantic ``UserIntent`` model with ``.intent_type`` attribute
        - dict with ``intent_type`` key
        - bare string
    """
    if intent is None:
        return False

    name: object | None = None
    if hasattr(intent, "intent_type"):
        name = getattr(intent, "intent_type")
    elif isinstance(intent, dict):
        name = intent.get("intent_type")
    else:
        name = intent

    if name is None:
        return False
    if hasattr(name, "value"):
        name = name.value
    if hasattr(name, "name"):
        name = name.name
    return str(name).upper() == "LIFE_EVENT"


def widen_intervals(
    forecast_matrix: np.ndarray,
    volatilities: dict[str, float] | None = None,
    active_intents: Iterable[object] | None = None,
) -> np.ndarray:
    """Inflate P10/P90 (and proportionally P2/P98, half-magnitude P25/P75)
    spread around the P50 median.

    Args:
        forecast_matrix: Shape ``(horizon, 7)`` — quantiles ordered
            ``[P02, P10, P25, P50, P75, P90, P98]`` (matches
            ``QuantileLoss`` defaults). ``P50`` is the median; the
            function preserves it unchanged.
        volatilities: Optional dict from
            :func:`compute_bucket_volatility`. When ``any(cv > threshold)``,
            a volatility bump is applied.
        active_intents: Optional iterable of user intents. Any
            LIFE_EVENT intent triggers an additive intent bump on top of
            the volatility bump.

    Returns:
        New array, same shape, with widened intervals. Always returns a
        copy — the input is not mutated.
    """
    forecast = np.asarray(forecast_matrix, dtype=float).copy()
    if forecast.ndim != 2 or forecast.shape[1] != 7:
        raise ValueError(f"forecast_matrix must be (horizon, 7), got {forecast.shape}")

    multiplier = 1.0
    if volatilities and any(cv > VOLATILITY_THRESHOLD_CV for cv in volatilities.values()):
        multiplier += SPREAD_BUMP_VOLATILITY

    if active_intents:
        if any(_intent_is_life_event(intent) for intent in active_intents):
            multiplier += SPREAD_BUMP_INTENT

    multiplier = min(multiplier, MAX_SPREAD_MULTIPLIER)
    if multiplier == 1.0:
        return forecast

    median = forecast[:, 3:4]  # P50 column kept as median anchor
    inner_scale = 1.0 + (multiplier - 1.0) * 0.5  # P25/P75 widen at half rate

    # Index map: 0=P02, 1=P10, 2=P25, 3=P50, 4=P75, 5=P90, 6=P98
    forecast[:, 0] = median[:, 0] + (forecast[:, 0] - median[:, 0]) * multiplier
    forecast[:, 1] = median[:, 0] + (forecast[:, 1] - median[:, 0]) * multiplier
    forecast[:, 2] = median[:, 0] + (forecast[:, 2] - median[:, 0]) * inner_scale
    # forecast[:, 3] unchanged (median)
    forecast[:, 4] = median[:, 0] + (forecast[:, 4] - median[:, 0]) * inner_scale
    forecast[:, 5] = median[:, 0] + (forecast[:, 5] - median[:, 0]) * multiplier
    forecast[:, 6] = median[:, 0] + (forecast[:, 6] - median[:, 0]) * multiplier

    return forecast
