"""Tests for the forecasting domain router.

Migrated from apps/api/tests/test_forecast.py to test the new domain router.
"""

import io
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.domains.forecasting.router import router
from apps.api.core.auth import get_user_client

# CSV with 50 days of data
CSV_50_DAYS = "Date,Amount,Description,Merchant\n"
for i in range(50):
    day = f"2026-01-{(i % 28) + 1:02d}" if i < 28 else f"2026-02-{(i - 27):02d}"
    CSV_50_DAYS += f"{day},{(-10.0 - i):.2f},Purchase {i},Store {i}\n"


def _make_mock_client():
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.user.id = "test-user-id"
    mock_client.auth.get_user.return_value = mock_user

    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])
    mock_table.select.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.order.return_value = mock_table
    return mock_client


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def mock_client(app):
    mock = _make_mock_client()
    app.dependency_overrides[get_user_client] = lambda: mock
    yield mock
    app.dependency_overrides.clear()


@pytest.fixture
def client(app):
    return TestClient(app)


def test_forecast_predict_returns_200(client):
    file = io.BytesIO(CSV_50_DAYS.encode("utf-8"))
    response = client.post(
        "/api/v1/forecast/predict",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    assert response.status_code == 200


def test_forecast_predict_returns_prediction_shape(client):
    file = io.BytesIO(CSV_50_DAYS.encode("utf-8"))
    response = client.post(
        "/api/v1/forecast/predict",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    data = response.json()
    assert "predictions" in data
    assert "horizon_days" in data
    assert data["horizon_days"] == 7


def test_forecast_safe_to_spend_returns_200(client):
    response = client.get("/api/v1/forecast/safe-to-spend")
    assert response.status_code == 200


def test_forecast_safe_to_spend_returns_amount(client):
    response = client.get("/api/v1/forecast/safe-to-spend")
    data = response.json()
    assert "safe_amount" in data
    assert isinstance(data["safe_amount"], (int, float))
