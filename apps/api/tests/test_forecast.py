"""Tests for the forecast endpoint."""
import io
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.deps import get_user_client

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

    # table("uploaded_files").insert(...).execute() succeeds
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    # table("transactions").select(...).gte(...).order(...).execute() returns empty
    mock_table.select.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.order.return_value = mock_table

    return mock_client


@pytest.fixture(autouse=True)
def override_auth():
    """Override auth dependency with a mock Supabase client."""
    mock_client = _make_mock_supabase()
    app.dependency_overrides[get_user_client] = lambda: mock_client
    yield mock_client
    app.dependency_overrides.clear()


client = TestClient(app)


def test_forecast_predict_returns_200():
    """POST transaction data and get a 200 with predictions."""
    file = io.BytesIO(CSV_50_DAYS.encode("utf-8"))
    response = client.post(
        "/api/v1/forecast/predict",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    assert response.status_code == 200


def test_forecast_predict_returns_prediction_shape():
    """Response should include forecast horizon and values."""
    file = io.BytesIO(CSV_50_DAYS.encode("utf-8"))
    response = client.post(
        "/api/v1/forecast/predict",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    data = response.json()
    assert "predictions" in data
    assert "horizon_days" in data
    assert data["horizon_days"] == 7


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
