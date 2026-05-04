"""Router test for POST /api/v1/forecast/scenario — LLD 010.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md §API Changes
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.core.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_user_client,
)
from apps.api.domains.forecasting.router import _get_service
from apps.api.domains.forecasting.schemas import (
    ForecastInsights,
    ForecastPoint,
    ForecastResponse,
    LowestBalance,
    QuantileSnapshot,
    ScenarioDelta,
    ScenarioResponse,
)
from apps.api.domains.forecasting.service import ForecastService
from apps.api.main import app


def _make_forecast() -> ForecastResponse:
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


@pytest.fixture(autouse=True)
def _cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def _make_empty_supabase_client() -> MagicMock:
    """Build a supabase client whose transactions select returns []."""
    client = MagicMock()
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=[])
    client.table.return_value = chain
    return client


def _override_auth():
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-id", email=None)
    app.dependency_overrides[get_user_client] = lambda: _make_empty_supabase_client()


def test_scenario_returns_scenario_response_shape():
    a = _make_forecast()
    b = _make_forecast()
    delta = ScenarioDelta(
        safe_to_spend=0.0,
        overdraft_risk_score=0.0,
        predicted_monthly_spend=0.0,
        predicted_monthly_income=0.0,
        month_end_p50_delta=0.0,
        confidence_band_width_delta=0.0,
    )
    sr = ScenarioResponse(
        with_intents=b,
        without_intents=a,
        delta=delta,
        applied_intents=[],
        excluded_intents=[],
    )

    svc = MagicMock(spec=ForecastService)
    svc.scenario_predict = AsyncMock(return_value=sr)

    _override_auth()
    app.dependency_overrides[_get_service] = lambda: svc

    with TestClient(app) as tc:
        app.state.scenario_rate_limiter = None
        resp = tc.post(
            "/api/v1/forecast/scenario",
            json={"horizon": 3, "intent_ids_to_exclude": [], "ephemeral_intents": []},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "with_intents" in body
    assert "without_intents" in body
    assert "delta" in body


def test_scenario_requires_authentication():
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as tc:
        app.state.scenario_rate_limiter = None
        resp = tc.post("/api/v1/forecast/scenario", json={"horizon": 3})
    assert resp.status_code == 401


def test_scenario_horizon_capped_at_30():
    _override_auth()
    svc = MagicMock(spec=ForecastService)
    app.dependency_overrides[_get_service] = lambda: svc
    with TestClient(app) as tc:
        app.state.scenario_rate_limiter = None
        resp = tc.post("/api/v1/forecast/scenario", json={"horizon": 60})
    assert resp.status_code == 422
