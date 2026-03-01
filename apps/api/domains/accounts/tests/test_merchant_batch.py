"""Tests for merchant-batch reclassification behavior."""
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
def mock_client_with_tx():
    """Mock Supabase client pre-loaded with one transaction."""
    mock = MagicMock()
    mock.auth.get_user.return_value = MagicMock(user=MagicMock(id="user-1"))

    tx = {
        "id": "tx-123",
        "user_id": "user-1",
        "description": "SWIGGY ORDER",
        "category": "Transport",
        "amount": -200.0,
        "is_manual": False,
    }

    # Chainable table mock — all methods return same mock
    tbl = MagicMock()
    mock.table.return_value = tbl
    tbl.update.return_value = tbl
    tbl.select.return_value = tbl
    tbl.eq.return_value = tbl
    tbl.ilike.return_value = tbl

    # First execute() → single-transaction update result
    tbl.execute.return_value = MagicMock(data=[tx])

    return mock


@pytest.fixture
def app_client(app, mock_client_with_tx):
    app.dependency_overrides[get_user_client] = lambda: mock_client_with_tx
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_reclassify_single_transaction_also_updates_merchant_matches(app_client):
    """PATCH /transactions/{id} must auto-update all matching merchant transactions."""
    response = app_client.patch(
        "/api/v1/accounts/transactions/tx-123",
        json={"category": "Food", "old_category": "Transport"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "merchant_updated" in data, (
        "Response must include 'merchant_updated' count — "
        "merchant-batch reclassification not implemented"
    )


def test_no_old_category_skips_merchant_batch(app_client):
    """When old_category is omitted, merchant-batch should not run (merchant_updated=0)."""
    response = app_client.patch(
        "/api/v1/accounts/transactions/tx-123",
        json={"category": "Food"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200
    data = response.json()
    # Either no key (legacy) or 0 — both acceptable as long as no crash
    assert data.get("merchant_updated", 0) == 0
