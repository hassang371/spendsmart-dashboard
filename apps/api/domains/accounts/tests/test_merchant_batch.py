"""Tests for merchant-batch reclassification behavior."""

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
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="user-1", email=None)
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
        "Response must include 'merchant_updated' count — " "merchant-batch reclassification not implemented"
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


def test_fine_tuning_triggered_after_merchant_batch():
    """After merchant-batch reclassification, supervised fine-tuning must be triggered."""
    import inspect

    from apps.api.domains.accounts import router as accounts_module

    src = inspect.getsource(accounts_module.update_transaction)
    assert "_run_supervised_finetuning_bg" in src, (
        "update_transaction must enqueue _run_supervised_finetuning_bg — "
        "supervised fine-tuning not triggered after reclassification"
    )


def test_merchant_name_used_for_batch_when_populated(app_client, mock_client_with_tx):
    """When tx has merchant_name, batch update must eq on merchant_name, not ilike description."""
    tx_with_merchant = {
        "id": "tx-123",
        "user_id": "user-1",
        "description": "SWIGGY ORDER",
        "merchant_name": "Swiggy",
        "category": "Transport",
        "amount": -200.0,
        "is_manual": False,
    }
    tbl = mock_client_with_tx.table.return_value
    tbl.execute.return_value = MagicMock(data=[tx_with_merchant])

    response = app_client.patch(
        "/api/v1/accounts/transactions/tx-123",
        json={"category": "Food", "old_category": "Transport"},
        headers={"Authorization": "Bearer fake"},
    )
    assert response.status_code == 200

    eq_calls = tbl.eq.call_args_list
    merchant_name_matched = any(call.args and call.args[0] == "merchant_name" for call in eq_calls)
    assert merchant_name_matched, "When merchant_name is populated, batch must match on merchant_name field"


def test_suggested_category_cleared_on_correction(app_client, mock_client_with_tx):
    """Correcting a category must clear suggested_category and confidence_score."""
    import inspect

    from apps.api.domains.accounts import router as accounts_module

    src = inspect.getsource(accounts_module.update_transaction)
    assert (
        "suggested_category" in src and "confidence_score" in src
    ), "update_transaction must clear suggested_category and confidence_score on correction"
