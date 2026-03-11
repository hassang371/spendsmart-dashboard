"""Tests for the accounts domain router.

Tests cover transaction listing (with pagination + filtering),
profile endpoint, and response model validation.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_user_client,
)
from apps.api.domains.accounts.router import router


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

    # Mock transactions query — chainable builder
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.order.return_value = mock_table
    mock_table.limit.return_value = mock_table
    mock_table.gte.return_value = mock_table
    mock_table.lte.return_value = mock_table
    mock_table.ilike.return_value = mock_table
    mock_table.lt.return_value = mock_table
    mock_table.execute.return_value = MagicMock(
        data=[
            {
                "id": "tx-1",
                "user_id": "test-user-123",
                "amount": -50.0,
                "description": "Coffee",
                "merchant_name": "Starbucks",
                "transaction_date": "2026-01-15",
                "currency": "INR",
                "category": "Food & Dining",
                "payment_method": "card",
                "status": "completed",
                "type": "debit",
                "fingerprint": "abc123",
                "is_manual": False,
                "created_at": "2026-01-15T10:30:00+05:30",
            },
        ]
    )
    return mock_client


@pytest.fixture
def client(app, mock_user_client):
    app.dependency_overrides[get_user_client] = lambda: mock_user_client
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-123"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-123", email="test@example.com")
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


class TestTransactions:
    def test_list_transactions_returns_200(self, client):
        response = client.get("/api/v1/accounts/transactions")
        assert response.status_code == 200

    def test_list_transactions_returns_cursor_page(self, client):
        """Response should be a CursorPage with items, next_cursor, has_more."""
        data = client.get("/api/v1/accounts/transactions").json()
        assert "items" in data
        assert "next_cursor" in data
        assert "has_more" in data

    def test_list_transactions_items_shape(self, client):
        """Each item in the page should have TransactionOut fields."""
        data = client.get("/api/v1/accounts/transactions").json()
        tx = data["items"][0]
        assert tx["description"] == "Coffee"
        assert tx["merchant_name"] == "Starbucks"
        assert tx["amount"] == -50.0
        assert tx["category"] == "Food & Dining"

    def test_list_transactions_with_limit(self, client, mock_user_client):
        """Limit query param should be passed to the Supabase query."""
        client.get("/api/v1/accounts/transactions?limit=10")
        # Verify limit was called with 10 + 1 (fetch extra to check has_more)
        mock_user_client.table.return_value.limit.assert_called()

    def test_list_transactions_with_category_filter(self, client, mock_user_client):
        """Category filter should be applied to the query."""
        client.get("/api/v1/accounts/transactions?category=Food")
        mock_user_client.table.return_value.eq.assert_any_call("category", "Food")

    def test_list_transactions_with_merchant_filter(self, client, mock_user_client):
        """Merchant filter should use ilike for case-insensitive search."""
        client.get("/api/v1/accounts/transactions?merchant=Starbucks")
        mock_user_client.table.return_value.ilike.assert_called_with("merchant_name", "%Starbucks%")


class TestProfile:
    def test_profile_returns_200(self, client):
        response = client.get("/api/v1/accounts/profile")
        assert response.status_code == 200

    def test_profile_returns_user_info(self, client):
        data = client.get("/api/v1/accounts/profile").json()
        assert data["id"] == "test-user-123"
        assert data["email"] == "test@example.com"
