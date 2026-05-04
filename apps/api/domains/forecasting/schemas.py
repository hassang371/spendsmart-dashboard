"""Forecasting domain schemas (RFC-003 §1 contract).

This module defines the Pydantic models for the v1 prediction-engine
forecast API. Stage 5 wires these into ``service.py`` / ``router.py``;
Stage 2 (this file) only establishes the contract so downstream stages
can build against a frozen shape.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §1
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# Allowed category buckets — kept in lockstep with packages.forecasting.buckets
# CATEGORY_BUCKETS and the SQL CHECK constraints on user_intents +
# scheduled_cashflows. Schema-level validation here gives a fast 400 instead
# of waiting for the DB CHECK to fire.
_ALLOWED_CATEGORY_BUCKETS: frozenset[str] = frozenset(
    {
        "salary",
        "rent",
        "groceries",
        "dining",
        "transport",
        "utilities",
        "entertainment",
        "health",
        "emi_loan",
        "investment",
        "transfer",
        "other",
    }
)

_RRULE_FREQS = ("monthly", "weekly", "biweekly", "quarterly", "annual")


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


# ---------------------------------------------------------------------------
# LLD 010 — User intents + scenario forecasting
# ---------------------------------------------------------------------------
#
# Refs: docs/features/010-user-intents-and-scenario-forecasting.md
#       §Domain Model
#
# `ScenarioResponse` references `ForecastResponse` directly. It MUST stay
# declared after `ForecastResponse` in this file; if a future refactor splits
# them, swap to ``ScenarioResponse.model_rebuild()`` after the import.


class IntentType(str, Enum):
    """Seven intent types per LLD 010."""

    INCOME_CHANGE = "income_change"
    PLANNED_LARGE_EXPENSE = "planned_large_expense"
    LIFE_EVENT = "life_event"
    OBLIGATION_CHANGE = "obligation_change"
    SAVINGS_GOAL = "savings_goal"
    FD_MATURITY = "fd_maturity"
    EXPECTED_BONUS = "expected_bonus"


class IntentConfidence(str, Enum):
    """Tiered confidence per LLD 010 §Design (Confidence interaction)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_DATED_INTENT_TYPES: frozenset[IntentType] = frozenset(
    {
        IntentType.INCOME_CHANGE,
        IntentType.PLANNED_LARGE_EXPENSE,
        IntentType.OBLIGATION_CHANGE,
        IntentType.FD_MATURITY,
        IntentType.EXPECTED_BONUS,
    }
)


def _validate_intent_cross_fields(values: Any) -> Any:
    """Cross-field validator shared by Create / full UserIntent.

    Mirrors the DB CHECK constraints on ``public.user_intents``:
    * Dated intent types require ``amount`` OR ``amount_delta``.
    * ``is_recurring=True`` requires ``rrule_freq``.
    * ``SAVINGS_GOAL`` requires ``end_date``.
    * ``amount_delta`` is allowed only on ``INCOME_CHANGE``.
    * ``category_bucket``, when given, must be in the allowlist.
    """
    if not isinstance(values, dict):
        return values

    intent_type = values.get("intent_type")
    if isinstance(intent_type, str):
        try:
            intent_type = IntentType(intent_type)
        except ValueError as exc:  # pragma: no cover - pydantic raises first
            raise ValueError(f"invalid intent_type: {intent_type}") from exc

    amount = values.get("amount")
    amount_delta = values.get("amount_delta")
    is_recurring = values.get("is_recurring")
    rrule_freq = values.get("rrule_freq")
    end_date = values.get("end_date")
    category_bucket = values.get("category_bucket")

    if intent_type in _DATED_INTENT_TYPES and amount is None and amount_delta is None:
        raise ValueError(f"{intent_type.value} requires `amount` or `amount_delta`")

    if is_recurring and not rrule_freq:
        raise ValueError("is_recurring=True requires rrule_freq")

    if intent_type is IntentType.SAVINGS_GOAL and end_date is None:
        raise ValueError("SAVINGS_GOAL requires end_date")

    if amount_delta is not None and intent_type is not IntentType.INCOME_CHANGE:
        raise ValueError("amount_delta is only valid on INCOME_CHANGE")

    if category_bucket is not None and category_bucket not in _ALLOWED_CATEGORY_BUCKETS:
        raise ValueError(f"category_bucket {category_bucket!r} not in allowed buckets")

    return values


class UserIntent(BaseModel):
    """Full read-shape of a row in ``public.user_intents``."""

    id: UUID
    user_id: UUID
    intent_type: IntentType
    amount: float | None = None
    amount_delta: float | None = None
    category_bucket: str | None = None
    start_date: date
    end_date: date | None = None
    confidence: IntentConfidence
    is_recurring: bool = False
    rrule_freq: Literal["monthly", "weekly", "biweekly", "quarterly", "annual"] | None = None
    notes: Annotated[str | None, Field(default=None, max_length=280)] = None
    is_active: bool = True
    created_at: str
    updated_at: str

    @model_validator(mode="before")
    @classmethod
    def _check_cross_fields(cls, values: Any) -> Any:
        return _validate_intent_cross_fields(values)


class IntentCreateRequest(BaseModel):
    """POST /forecast/intents body."""

    intent_type: IntentType
    amount: float | None = None
    amount_delta: float | None = None
    category_bucket: str | None = None
    start_date: date
    end_date: date | None = None
    confidence: IntentConfidence = IntentConfidence.MEDIUM
    is_recurring: bool = False
    rrule_freq: Literal["monthly", "weekly", "biweekly", "quarterly", "annual"] | None = None
    notes: Annotated[str | None, Field(default=None, max_length=280)] = None

    @model_validator(mode="before")
    @classmethod
    def _check_cross_fields(cls, values: Any) -> Any:
        return _validate_intent_cross_fields(values)


class IntentUpdateRequest(BaseModel):
    """PATCH /forecast/intents/{id} body — all fields optional."""

    amount: float | None = None
    amount_delta: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    confidence: IntentConfidence | None = None
    notes: Annotated[str | None, Field(default=None, max_length=280)] = None
    is_active: bool | None = None


class ScenarioRequest(BaseModel):
    """POST /forecast/scenario body."""

    horizon: Annotated[int, Field(ge=1, le=30)] = 30
    intent_ids_to_exclude: list[UUID] = Field(default_factory=list)
    ephemeral_intents: Annotated[list[IntentCreateRequest], Field(max_length=20)] = Field(default_factory=list)


class ScenarioDelta(BaseModel):
    """Per-field delta (B − A) on the comparable insights metrics."""

    safe_to_spend: float
    overdraft_risk_score: float
    predicted_monthly_spend: float
    predicted_monthly_income: float
    month_end_p50_delta: float
    confidence_band_width_delta: float


class ScenarioResponse(BaseModel):
    """A/B forecast comparison + delta — see LLD 010 §Scenario Endpoint Design."""

    with_intents: ForecastResponse
    without_intents: ForecastResponse
    delta: ScenarioDelta
    applied_intents: list[UserIntent] = Field(default_factory=list)
    excluded_intents: list[UserIntent] = Field(default_factory=list)
