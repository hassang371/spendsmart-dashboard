# apps/api/domains/aggregator/tests/test_router.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.domains.aggregator.router import router


@pytest.fixture
def mock_client():
    client = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[])
    for m in ("eq", "order", "select", "insert", "update", "delete"):
        getattr(chain, m).return_value = chain
    client.table.return_value = chain
    return client


@pytest.fixture
def app(mock_client):
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")
    test_app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    test_app.dependency_overrides[get_user_client] = lambda: mock_client
    return test_app


@pytest.fixture
def http(app):
    return TestClient(app)


def test_list_accounts(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {
            "id": "acc-1",
            "user_id": "test-user-id",
            "account_name": "Savings",
            "account_type": "DEPOSIT",
            "consent_status": "ACTIVE",
            "sync_status": "idle",
            "is_primary": True,
            "is_manual": False,
            "currency": "INR",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
    ]
    assert http.get("/api/v1/aggregator/accounts/").status_code == 200


def test_get_account(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "acc-1"}
    ]
    assert http.get("/api/v1/aggregator/accounts/acc-1").status_code == 200


def test_link_account(http):
    with patch("apps.api.domains.aggregator.router._get_setu_provider") as mp:
        p = AsyncMock()
        p.initiate_consent.return_value = {"consent_id": "c-1", "redirect_url": "https://setu.co/c-1"}
        mp.return_value = p
        resp = http.post("/api/v1/aggregator/accounts/link", json={"fi_types": ["DEPOSIT"]})
        assert resp.status_code == 200
        assert resp.json()["consent_id"] == "c-1"


def test_delete_account(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "acc-1", "is_manual": False, "consent_id": "c-1", "consent_status": "active"}
    ]
    with patch("apps.api.domains.aggregator.router._get_setu_provider") as mp:
        mp.return_value = AsyncMock()
        assert http.delete("/api/v1/aggregator/accounts/acc-1").status_code == 204


def test_consent_callback(http, mock_client):
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"id": "acc-1", "user_id": "test-user-id"}
    ]
    with patch("apps.api.domains.aggregator.router._get_setu_provider") as mp:
        p = AsyncMock()
        p.check_consent_status.return_value = {"status": "ACTIVE", "detail": {}}
        mp.return_value = p
        assert http.get("/api/v1/aggregator/accounts/callback?consent_id=c-1").status_code == 200
