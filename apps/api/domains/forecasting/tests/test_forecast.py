"""Tests for the forecast endpoint.

Stage 5: response shape was migrated from the legacy ``{predictions:
[...]}`` dict to the RFC-003 ``ForecastResponse``. These tests assert
the new shape and stub the Chronos engine (chronos-forecasting is not
a CI dep).
"""

import io
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from apps.api.core.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_user_client,
)
from apps.api.main import app

# CSV with enough data points for the forecasting engine
# Need at least 37 days (30 context + 7 prediction) for TFT
CSV_50_DAYS = "Date,Amount,Description,Merchant\n"
for i in range(50):
    day = f"2026-01-{(i % 28) + 1:02d}" if i < 28 else f"2026-02-{(i - 27):02d}"
    CSV_50_DAYS += f"{day},{(-10.0 - i):.2f},Purchase {i},Store {i}\n"


def _make_mock_supabase():
    """Create a mock Supabase client that satisfies forecast endpoints."""
    mock_client = MagicMock()

    # auth.get_user() returns a user with an id
    mock_user = MagicMock()
    mock_user.user.id = "test-user-id"
    mock_client.auth.get_user.return_value = mock_user

    # Full chainable query mock — supports .select().eq().eq().gte().order().limit().execute()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.select.return_value = mock_table
    # BUG-002: .eq() is now called in safe-to-spend for user_id filtering
    mock_table.eq.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    # Return empty transactions — safe-to-spend handles empty gracefully
    mock_table.execute.return_value = MagicMock(data=[])

    return mock_client


@pytest.fixture(autouse=True)
def override_auth():
    """Override auth dependency with a mock Supabase client."""
    mock_client = _make_mock_supabase()
    app.dependency_overrides[get_user_client] = lambda: mock_client
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-id", email=None)
    yield mock_client
    app.dependency_overrides.clear()


client = TestClient(app)


def _stub_chronos():
    """Stub ChronosEngine so tests don't require chronos-forecasting installed."""
    chronos = MagicMock()
    forecast = []
    for i in range(30):
        forecast.append(
            {
                "date": (pd.Timestamp("2026-04-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
                "p2": 1000.0,
                "p10": 1100.0,
                "p25": 1200.0,
                "p50": 1300.0,
                "p75": 1400.0,
                "p90": 1500.0,
                "p98": 1600.0,
            }
        )
    chronos.predict.return_value = {
        "forecast": forecast,
        "model_type": "chronos2",
        "model_version": "chronos-2-small",
        "horizon": 30,
    }
    return chronos


def test_forecast_predict_returns_200():
    """POST transaction data → 200 with ForecastResponse."""
    file = io.BytesIO(CSV_50_DAYS.encode("utf-8"))
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=_stub_chronos()):
        response = client.post(
            "/api/v1/forecast/predict",
            files={"file": ("transactions.csv", file, "text/csv")},
        )
    assert response.status_code == 200, response.text


def test_forecast_predict_returns_prediction_shape():
    """Response carries the RFC-003 ForecastResponse fields."""
    file = io.BytesIO(CSV_50_DAYS.encode("utf-8"))
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=_stub_chronos()):
        response = client.post(
            "/api/v1/forecast/predict",
            files={"file": ("transactions.csv", file, "text/csv")},
        )
    data = response.json()
    assert "forecast" in data
    assert "horizon" in data
    assert "model_type" in data
    assert "insights" in data
    assert "prediction_id" in data
    assert data["horizon"] == 30


def test_forecast_safe_to_spend_returns_200():
    """GET safe-to-spend should return 200 with a safe amount."""
    response = client.get("/api/v1/forecast/safe-to-spend")
    assert response.status_code == 200


def test_forecast_safe_to_spend_returns_amount():
    """Response should include a safe_amount field."""
    response = client.get("/api/v1/forecast/safe-to-spend")
    data = response.json()
    assert "safe_amount" in data
    assert isinstance(data["safe_amount"], (int, float))
