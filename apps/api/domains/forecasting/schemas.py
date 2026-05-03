"""Forecasting domain schemas (RFC-003 §1 contract).

This module defines the Pydantic models for the v1 prediction-engine
forecast API. Stage 5 wires these into ``service.py`` / ``router.py``;
Stage 2 (this file) only establishes the contract so downstream stages
can build against a frozen shape.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §1
"""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    """One predicted day's full 7-quantile distribution.

    All 7 quantiles are required floats. Both tiers (TFT-Hybrid and
    Chronos-2) emit the same 7-quantile set; see RFC-003
    §"Chronos-path quantile expansion" for the engine upgrade that makes
    this true.
    """

    date: str  # "YYYY-MM-DD"
    p2: float
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    p98: float


class VariableImportance(BaseModel):
    """One ``(feature, weight)`` pair from the TFT Variable Selection Network.

    Used both for the full ``ForecastResponse.variable_importance`` list
    (every feature the VSN reports) and for the top-3 subset surfaced in
    ``ForecastInsights.primary_drivers``. Empty for Chronos-only forecasts.
    """

    feature: str
    weight: float


class QuantileSnapshot(BaseModel):
    """A point-in-time snapshot of the P10/P50/P90 distribution."""

    p10: float
    p50: float
    p90: float


class LowestBalance(BaseModel):
    """The horizon day where P10 is minimised, plus its P10/P50."""

    date: str
    p10: float
    p50: float


class ForecastInsights(BaseModel):
    """Server-computed derived insights for one forecast call.

    See RFC-003 §1 for field semantics. ``floor_source`` is constrained
    to the two recognised provenances; v1 only emits
    ``"auto_p10_history"`` (override slot reserved for v1.5).
    """

    lowest_balance: LowestBalance
    month_end: QuantileSnapshot  # day 30 of horizon (rolling, not calendar)
    predicted_monthly_spend: float  # sum of negative P50 daily deltas over horizon
    predicted_monthly_income: float  # sum of positive P50 daily deltas over horizon
    confidence_band_width: float  # mean (P90 - P10) across horizon
    primary_drivers: list[VariableImportance]  # top 3 from VSN; empty for chronos2
    safe_to_spend: float  # largest spend such that all P10 days >= floor_used
    overdraft_risk_score: float  # fraction of horizon days with P10 < floor_used, [0, 1]
    floor_used: float  # floor value applied
    floor_source: Literal["auto_p10_history", "user_override"]


class ForecastResponse(BaseModel):
    """Full forecast payload returned by both predict endpoints."""

    forecast: Annotated[list[ForecastPoint], Field(min_length=1, max_length=30)]
    model_type: Literal["chronos2", "tft_hybrid", "ensemble"]
    model_version: str
    horizon: Annotated[int, Field(ge=1, le=30)]
    confidence: Literal["low", "medium", "high"]
    variable_importance: list[VariableImportance] | None
    insights: ForecastInsights
    prediction_id: UUID  # generated in ForecastService BEFORE the fire-and-forget INSERT


class TrainRequest(BaseModel):
    """POST /forecast/train body."""

    force: bool = False


class TrainStatusResponse(BaseModel):
    """GET /forecast/train/status response."""

    status: Literal["no_model", "pending", "claimed", "processing", "completed", "failed"]
    last_trained: str | None = None
    checkpoint_path: str | None = None
    training_days: int | None = None
