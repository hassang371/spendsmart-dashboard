"""LLD 010 intent → scheduled_cashflows bridge unit tests.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md
      §Intent → scheduled_cashflows Bridge
"""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest

from apps.api.domains.forecasting.schemas import (
    IntentConfidence,
    IntentType,
    UserIntent,
)
from packages.forecasting.intent_bridge import (
    CONFIDENCE_COVARIATE_WEIGHT,
    intent_to_scheduled_cashflow_row,
    should_have_bridge_row,
)


def _make_intent(
    *,
    intent_type: IntentType,
    amount: float | None = None,
    amount_delta: float | None = None,
    confidence: IntentConfidence = IntentConfidence.HIGH,
    is_active: bool = True,
    category_bucket: str | None = None,
    rrule_freq: str | None = None,
    end_date: date | None = None,
) -> UserIntent:
    return UserIntent(
        id=uuid4(),
        user_id=uuid4(),
        intent_type=intent_type,
        amount=amount,
        amount_delta=amount_delta,
        category_bucket=category_bucket,
        start_date=date(2026, 5, 15),
        end_date=end_date,
        confidence=confidence,
        is_recurring=False,
        rrule_freq=rrule_freq,
        notes=None,
        is_active=is_active,
        created_at="2026-04-17T00:00:00+00:00",
        updated_at="2026-04-17T00:00:00+00:00",
    )


# ---------------------------------------------------------------------------
# Confidence weights
# ---------------------------------------------------------------------------


def test_confidence_weights():
    assert CONFIDENCE_COVARIATE_WEIGHT[IntentConfidence.HIGH] == 1.0
    assert CONFIDENCE_COVARIATE_WEIGHT[IntentConfidence.MEDIUM] == 0.7
    assert CONFIDENCE_COVARIATE_WEIGHT[IntentConfidence.LOW] == 0.0


# ---------------------------------------------------------------------------
# should_have_bridge_row — table-driven
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("intent_type", "expected"),
    [
        (IntentType.INCOME_CHANGE, True),
        (IntentType.PLANNED_LARGE_EXPENSE, True),
        (IntentType.OBLIGATION_CHANGE, True),
        (IntentType.FD_MATURITY, True),
        (IntentType.EXPECTED_BONUS, True),
        (IntentType.LIFE_EVENT, False),
        (IntentType.SAVINGS_GOAL, False),
    ],
)
def test_should_have_bridge_row_table(intent_type: IntentType, expected: bool):
    if intent_type is IntentType.SAVINGS_GOAL:
        intent = _make_intent(intent_type=intent_type, end_date=date(2026, 12, 31))
    elif intent_type is IntentType.INCOME_CHANGE:
        intent = _make_intent(intent_type=intent_type, amount_delta=10000.0)
    elif intent_type is IntentType.LIFE_EVENT:
        intent = _make_intent(intent_type=intent_type)
    else:
        intent = _make_intent(intent_type=intent_type, amount=1000.0)
    assert should_have_bridge_row(intent) is expected


def test_should_have_bridge_row_independent_of_is_active():
    """Soft-deletes still keep the bridge row decision; LLD 010 H5."""
    intent = _make_intent(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=1000.0,
        is_active=False,
    )
    assert should_have_bridge_row(intent) is True


# ---------------------------------------------------------------------------
# intent_to_scheduled_cashflow_row
# ---------------------------------------------------------------------------


def test_bridge_row_high_confidence_full_amount_negative_for_expense():
    intent = _make_intent(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=80000.0,
        confidence=IntentConfidence.HIGH,
        category_bucket="entertainment",
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["amount"] == -80000.0
    assert row["category_bucket"] == "entertainment"
    assert row["source"] == "intent"
    assert row["next_occurrence"] == intent.start_date
    assert row["user_id"] == intent.user_id
    assert row["confidence"] == 1.0  # regularity, not user-intent confidence


def test_bridge_row_medium_confidence_70_percent_amount():
    intent = _make_intent(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=10000.0,
        confidence=IntentConfidence.MEDIUM,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["amount"] == pytest.approx(-7000.0)


def test_bridge_row_low_confidence_zero_amount():
    intent = _make_intent(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=10000.0,
        confidence=IntentConfidence.LOW,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["amount"] == 0.0


def test_bridge_row_income_change_uses_amount_delta_positive():
    intent = _make_intent(
        intent_type=IntentType.INCOME_CHANGE,
        amount_delta=20000.0,
        confidence=IntentConfidence.HIGH,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["amount"] == 20000.0


def test_bridge_row_obligation_change_negative():
    intent = _make_intent(
        intent_type=IntentType.OBLIGATION_CHANGE,
        amount=5000.0,
        confidence=IntentConfidence.HIGH,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["amount"] == -5000.0


def test_bridge_row_fd_maturity_positive():
    intent = _make_intent(
        intent_type=IntentType.FD_MATURITY,
        amount=100000.0,
        confidence=IntentConfidence.HIGH,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["amount"] == 100000.0


def test_bridge_row_expected_bonus_positive():
    intent = _make_intent(
        intent_type=IntentType.EXPECTED_BONUS,
        amount=50000.0,
        confidence=IntentConfidence.HIGH,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["amount"] == 50000.0


def test_bridge_row_default_rrule_is_monthly():
    intent = _make_intent(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=1000.0,
        confidence=IntentConfidence.HIGH,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["rrule_freq"] == "monthly"


def test_bridge_row_uses_explicit_rrule_when_set():
    intent = UserIntent(
        id=uuid4(),
        user_id=uuid4(),
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=1000.0,
        amount_delta=None,
        category_bucket=None,
        start_date=date(2026, 5, 15),
        end_date=date(2027, 5, 15),
        confidence=IntentConfidence.HIGH,
        is_recurring=True,
        rrule_freq="weekly",
        notes=None,
        is_active=True,
        created_at="2026-04-17T00:00:00+00:00",
        updated_at="2026-04-17T00:00:00+00:00",
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["rrule_freq"] == "weekly"


def test_bridge_row_default_category_bucket_inferred():
    intent = _make_intent(
        intent_type=IntentType.OBLIGATION_CHANGE,
        amount=5000.0,
        confidence=IntentConfidence.HIGH,
        category_bucket=None,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    # Default for OBLIGATION_CHANGE → some valid bucket; just assert it's set.
    from packages.forecasting.buckets import CATEGORY_BUCKETS

    assert row["category_bucket"] in CATEGORY_BUCKETS


def test_bridge_row_inactive_intent_mirrors_is_active():
    intent = _make_intent(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=1000.0,
        confidence=IntentConfidence.HIGH,
        is_active=False,
    )
    row = intent_to_scheduled_cashflow_row(intent)
    assert row["is_active"] is False
    assert row["source"] == "intent"
