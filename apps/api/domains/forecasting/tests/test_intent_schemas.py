"""Pydantic-level validation tests for LLD 010 user-intent schemas.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md §Domain Model
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from apps.api.domains.forecasting.schemas import (
    ForecastResponse,
    IntentConfidence,
    IntentCreateRequest,
    IntentType,
    IntentUpdateRequest,
    ScenarioDelta,
    ScenarioRequest,
    ScenarioResponse,
    UserIntent,
)

# ---------------------------------------------------------------------------
# IntentType / IntentConfidence enums
# ---------------------------------------------------------------------------


def test_intent_type_has_seven_members():
    expected = {
        "income_change",
        "planned_large_expense",
        "life_event",
        "obligation_change",
        "savings_goal",
        "fd_maturity",
        "expected_bonus",
    }
    assert {t.value for t in IntentType} == expected


def test_intent_confidence_has_three_members():
    assert {c.value for c in IntentConfidence} == {"low", "medium", "high"}


# ---------------------------------------------------------------------------
# IntentCreateRequest
# ---------------------------------------------------------------------------


def test_intent_create_minimal_dated_intent():
    req = IntentCreateRequest(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=80000.0,
        start_date=date(2026, 5, 15),
    )
    assert req.confidence == IntentConfidence.MEDIUM
    assert req.is_recurring is False


def test_intent_create_life_event_amount_optional():
    req = IntentCreateRequest(
        intent_type=IntentType.LIFE_EVENT,
        start_date=date(2026, 8, 1),
        confidence=IntentConfidence.HIGH,
    )
    assert req.amount is None


def test_intent_create_savings_goal_requires_end_date():
    with pytest.raises(ValidationError):
        IntentCreateRequest(
            intent_type=IntentType.SAVINGS_GOAL,
            start_date=date(2026, 5, 1),
            # missing end_date
        )


def test_intent_create_dated_requires_amount_or_delta():
    with pytest.raises(ValidationError):
        IntentCreateRequest(
            intent_type=IntentType.INCOME_CHANGE,
            start_date=date(2026, 5, 1),
            # neither amount nor amount_delta
        )


def test_intent_create_recurring_requires_rrule_freq():
    with pytest.raises(ValidationError):
        IntentCreateRequest(
            intent_type=IntentType.PLANNED_LARGE_EXPENSE,
            amount=1000.0,
            start_date=date(2026, 5, 1),
            is_recurring=True,
            # missing rrule_freq
        )


def test_intent_create_amount_delta_only_on_income_change():
    with pytest.raises(ValidationError):
        IntentCreateRequest(
            intent_type=IntentType.PLANNED_LARGE_EXPENSE,
            amount=1000.0,
            amount_delta=500.0,
            start_date=date(2026, 5, 1),
        )


def test_intent_create_invalid_category_bucket_rejected():
    with pytest.raises(ValidationError):
        IntentCreateRequest(
            intent_type=IntentType.PLANNED_LARGE_EXPENSE,
            amount=1000.0,
            start_date=date(2026, 5, 1),
            category_bucket="not_a_real_bucket",
        )


def test_intent_create_notes_capped_at_280_chars():
    with pytest.raises(ValidationError):
        IntentCreateRequest(
            intent_type=IntentType.PLANNED_LARGE_EXPENSE,
            amount=1.0,
            start_date=date(2026, 5, 1),
            notes="x" * 281,
        )


# ---------------------------------------------------------------------------
# UserIntent (full read shape)
# ---------------------------------------------------------------------------


def test_user_intent_round_trip():
    payload = {
        "id": str(uuid4()),
        "user_id": str(uuid4()),
        "intent_type": "planned_large_expense",
        "amount": 80000.0,
        "amount_delta": None,
        "category_bucket": "entertainment",
        "start_date": "2026-05-15",
        "end_date": None,
        "confidence": "high",
        "is_recurring": False,
        "rrule_freq": None,
        "notes": "Goa trip",
        "is_active": True,
        "created_at": "2026-04-17T00:00:00+00:00",
        "updated_at": "2026-04-17T00:00:00+00:00",
    }
    intent = UserIntent(**payload)
    assert intent.intent_type is IntentType.PLANNED_LARGE_EXPENSE
    assert intent.confidence is IntentConfidence.HIGH


# ---------------------------------------------------------------------------
# IntentUpdateRequest
# ---------------------------------------------------------------------------


def test_intent_update_all_fields_optional():
    req = IntentUpdateRequest()
    assert req.amount is None
    assert req.is_active is None


def test_intent_update_partial_payload():
    req = IntentUpdateRequest(is_active=False, confidence=IntentConfidence.LOW)
    assert req.is_active is False
    assert req.confidence is IntentConfidence.LOW


# ---------------------------------------------------------------------------
# ScenarioRequest
# ---------------------------------------------------------------------------


def test_scenario_request_defaults():
    req = ScenarioRequest()
    assert req.horizon == 30
    assert req.intent_ids_to_exclude == []
    assert req.ephemeral_intents == []


def test_scenario_request_horizon_capped_at_30():
    with pytest.raises(ValidationError):
        ScenarioRequest(horizon=31)


def test_scenario_request_horizon_min_1():
    with pytest.raises(ValidationError):
        ScenarioRequest(horizon=0)


def test_scenario_request_ephemeral_intents_capped_at_20():
    one_intent = IntentCreateRequest(
        intent_type=IntentType.LIFE_EVENT,
        start_date=date(2026, 5, 15),
    )
    with pytest.raises(ValidationError):
        ScenarioRequest(ephemeral_intents=[one_intent for _ in range(21)])


# ---------------------------------------------------------------------------
# ScenarioDelta + ScenarioResponse
# ---------------------------------------------------------------------------


def test_scenario_delta_all_fields_required():
    d = ScenarioDelta(
        safe_to_spend=10.0,
        overdraft_risk_score=-0.05,
        predicted_monthly_spend=-500.0,
        predicted_monthly_income=0.0,
        month_end_p50_delta=200.0,
        confidence_band_width_delta=15.0,
    )
    assert d.safe_to_spend == 10.0


def test_scenario_response_embeds_two_forecasts(forecast_response_factory):
    a = forecast_response_factory()
    b = forecast_response_factory()
    delta = ScenarioDelta(
        safe_to_spend=0.0,
        overdraft_risk_score=0.0,
        predicted_monthly_spend=0.0,
        predicted_monthly_income=0.0,
        month_end_p50_delta=0.0,
        confidence_band_width_delta=0.0,
    )
    resp = ScenarioResponse(
        with_intents=b,
        without_intents=a,
        delta=delta,
        applied_intents=[],
        excluded_intents=[],
    )
    assert isinstance(resp.with_intents, ForecastResponse)
    assert isinstance(resp.without_intents, ForecastResponse)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def forecast_response_factory():
    """Build a minimally-valid ForecastResponse for embedding tests."""
    from apps.api.domains.forecasting.schemas import (
        ForecastInsights,
        ForecastPoint,
        LowestBalance,
        QuantileSnapshot,
    )

    def _make() -> ForecastResponse:
        today = date.today()
        return ForecastResponse(
            forecast=[
                ForecastPoint(
                    date=(today + timedelta(days=i)).isoformat(),
                    p2=1.0,
                    p10=2.0,
                    p25=3.0,
                    p50=4.0,
                    p75=5.0,
                    p90=6.0,
                    p98=7.0,
                )
                for i in range(3)
            ],
            model_type="chronos2",
            model_version="chronos-2-small",
            horizon=3,
            confidence="medium",
            variable_importance=None,
            insights=ForecastInsights(
                lowest_balance=LowestBalance(date=today.isoformat(), p10=2.0, p50=4.0),
                month_end=QuantileSnapshot(p10=2.0, p50=4.0, p90=6.0),
                predicted_monthly_spend=0.0,
                predicted_monthly_income=0.0,
                confidence_band_width=4.0,
                primary_drivers=[],
                safe_to_spend=10.0,
                overdraft_risk_score=0.0,
                floor_used=0.0,
                floor_source="auto_p10_history",
            ),
            prediction_id=uuid4(),
        )

    return _make
