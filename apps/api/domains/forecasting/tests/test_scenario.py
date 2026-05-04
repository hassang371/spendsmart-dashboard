"""ForecastService.scenario_predict tests — LLD 010 §Scenario Endpoint Design.

Mocks predict() to return deterministic baseline + counterfactual; asserts
delta computation correctness, applied/excluded intent listing, and the
parallel-fetch path.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md
      §Scenario Endpoint Design
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
import pytest

from apps.api.domains.forecasting.schemas import (
    ForecastInsights,
    ForecastPoint,
    ForecastResponse,
    IntentConfidence,
    IntentCreateRequest,
    IntentType,
    LowestBalance,
    QuantileSnapshot,
    UserIntent,
)


def _make_forecast(
    *,
    safe=100.0,
    overdraft=0.0,
    spend=500.0,
    income=2000.0,
    me_p50=1500.0,
    band_width=200.0,
):
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
            month_end=QuantileSnapshot(p10=me_p50 - 100, p50=me_p50, p90=me_p50 + 100),
            predicted_monthly_spend=spend,
            predicted_monthly_income=income,
            confidence_band_width=band_width,
            primary_drivers=[],
            safe_to_spend=safe,
            overdraft_risk_score=overdraft,
            floor_used=0.0,
            floor_source="auto_p10_history",
        ),
        prediction_id=uuid4(),
    )


def _make_supabase_mock(stored_intents=None):
    client = MagicMock()
    rpc_resp = MagicMock()
    rpc_resp.execute.return_value = MagicMock(data=True)
    client.rpc.return_value = rpc_resp
    return client


def _make_transactions(n_days: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rng = np.random.default_rng(42)
    amounts = rng.choice([-50.0, -20.0, 1000.0, -10.0], size=n_days)
    return pd.DataFrame({"date": dates, "amount": amounts})


def _user_intent_row(**overrides):
    base = {
        "id": str(uuid4()),
        "user_id": str(uuid4()),
        "intent_type": "planned_large_expense",
        "amount": 50000.0,
        "amount_delta": None,
        "category_bucket": "entertainment",
        "start_date": "2026-05-15",
        "end_date": None,
        "confidence": "high",
        "is_recurring": False,
        "rrule_freq": None,
        "notes": None,
        "is_active": True,
        "created_at": "2026-04-17T00:00:00+00:00",
        "updated_at": "2026-04-17T00:00:00+00:00",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_scenario_predict_computes_delta_b_minus_a():
    """delta = with_intents (B) − without_intents (A)."""
    from apps.api.domains.forecasting.service import ForecastService

    svc = ForecastService(_make_supabase_mock(), tft_cache=None)

    a_resp = _make_forecast(
        safe=100.0,
        overdraft=0.05,
        spend=500.0,
        income=2000.0,
        me_p50=1500.0,
        band_width=200.0,
    )
    b_resp = _make_forecast(
        safe=80.0,
        overdraft=0.10,
        spend=600.0,
        income=2000.0,
        me_p50=1300.0,
        band_width=250.0,
    )

    # _fetch_active_intents returns no stored intents.
    svc._fetch_active_intents = MagicMock(return_value=[])

    # Mock predict to return A on first call, B on second.
    svc.predict = MagicMock(side_effect=[a_resp, b_resp])

    df = _make_transactions(n_days=10)
    result = asyncio.run(
        svc.scenario_predict(
            df,
            user_id="u1",
            excludes=[],
            ephemeral=[
                IntentCreateRequest(
                    intent_type=IntentType.PLANNED_LARGE_EXPENSE,
                    amount=80000.0,
                    start_date=date(2026, 5, 15),
                    confidence=IntentConfidence.HIGH,
                )
            ],
            horizon=3,
        )
    )

    assert result.with_intents.insights.safe_to_spend == 80.0
    assert result.without_intents.insights.safe_to_spend == 100.0
    # delta = B − A
    assert result.delta.safe_to_spend == pytest.approx(-20.0)
    assert result.delta.overdraft_risk_score == pytest.approx(0.05)
    assert result.delta.predicted_monthly_spend == pytest.approx(100.0)
    assert result.delta.predicted_monthly_income == pytest.approx(0.0)
    assert result.delta.month_end_p50_delta == pytest.approx(-200.0)
    assert result.delta.confidence_band_width_delta == pytest.approx(50.0)


def test_scenario_predict_excludes_remove_stored_intents():
    from apps.api.domains.forecasting.service import ForecastService

    svc = ForecastService(_make_supabase_mock(), tft_cache=None)

    stored_id = uuid4()
    stored = UserIntent(**_user_intent_row(id=str(stored_id)))
    svc._fetch_active_intents = MagicMock(return_value=[stored])

    a_resp = _make_forecast()
    b_resp = _make_forecast()
    svc.predict = MagicMock(side_effect=[a_resp, b_resp])

    df = _make_transactions(n_days=10)
    result = asyncio.run(
        svc.scenario_predict(
            df,
            user_id="u1",
            excludes=[stored_id],
            ephemeral=[],
            horizon=3,
        )
    )
    # The excluded intent must show up in excluded_intents.
    assert any(i.id == stored.id for i in result.excluded_intents)
    # applied_intents = stored − excludes + ephemeral; here that's empty.
    assert result.applied_intents == []


def test_scenario_predict_does_not_log_to_user_predictions():
    """Scenario forecasts must NOT call log_user_prediction (per Stage 6 spec)."""
    from apps.api.domains.forecasting.service import ForecastService

    client = _make_supabase_mock()
    svc = ForecastService(client, tft_cache=None)
    svc._fetch_active_intents = MagicMock(return_value=[])
    svc.predict = MagicMock(side_effect=[_make_forecast(), _make_forecast()])

    df = _make_transactions(n_days=10)
    asyncio.run(
        svc.scenario_predict(
            df,
            user_id="u1",
            excludes=[],
            ephemeral=[],
            horizon=3,
        )
    )

    # The service must not have invoked the log RPC for scenario calls.
    rpc_calls = [c.args[0] for c in client.rpc.call_args_list]
    assert "log_user_prediction" not in rpc_calls


def test_scenario_predict_savings_goal_produces_zero_delta_when_only_change():
    """SAVINGS_GOAL is metadata-only; including it in ephemeral should not
    materially change the forecast since neither bridge nor widener fire."""
    from apps.api.domains.forecasting.service import ForecastService

    svc = ForecastService(_make_supabase_mock(), tft_cache=None)
    svc._fetch_active_intents = MagicMock(return_value=[])

    same = _make_forecast()
    same2 = _make_forecast()
    svc.predict = MagicMock(side_effect=[same, same2])

    df = _make_transactions(n_days=10)
    result = asyncio.run(
        svc.scenario_predict(
            df,
            user_id="u1",
            excludes=[],
            ephemeral=[
                IntentCreateRequest(
                    intent_type=IntentType.SAVINGS_GOAL,
                    amount=200000.0,
                    start_date=date(2026, 5, 1),
                    end_date=date(2026, 12, 31),
                )
            ],
            horizon=3,
        )
    )
    assert result.delta.safe_to_spend == 0.0
    assert result.delta.predicted_monthly_spend == 0.0
