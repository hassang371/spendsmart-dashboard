"""Tests for the accounts domain router."""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.domains.accounts.router import router
from apps.api.core.auth import get_user_client


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_user_client():
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "test-user-123"
    mock_user.email = "test@example.com"
    mock_client.auth.get_user.return_value = MagicMock(user=mock_user)

    # Mock transactions query
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[
        {
            "id": "tx-1",
            "amount": -50.0,
            "description": "Coffee",
            "merchant_name": "Starbucks",
            "transaction_date": "2026-01-15",
        },
    ])
    return mock_client


@pytest.fixture
def client(app, mock_user_client):
    app.dependency_overrides[get_user_client] = lambda: mock_user_client
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class TestTransactions:
    def test_list_transactions_returns_200(self, client):
        response = client.get("/api/v1/accounts/transactions")
        assert response.status_code == 200

    def test_list_transactions_returns_data(self, client):
        response = client.get("/api/v1/accounts/transactions")
        data = response.json()
        assert "transactions" in data
        assert "count" in data
        assert data["count"] == 1

    def test_list_transactions_shape(self, client):
        data = client.get("/api/v1/accounts/transactions").json()
        tx = data["transactions"][0]
        assert tx["description"] == "Coffee"
        assert tx["merchant_name"] == "Starbucks"


class TestProfile:
    def test_profile_returns_200(self, client):
        response = client.get("/api/v1/accounts/profile")
        assert response.status_code == 200

    def test_profile_returns_user_info(self, client):
        data = client.get("/api/v1/accounts/profile").json()
        assert data["id"] == "test-user-123"
        assert data["email"] == "test@example.com"
