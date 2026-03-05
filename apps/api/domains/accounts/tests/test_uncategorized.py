import pytest
from fastapi.testclient import TestClient
from apps.api.main import app
from apps.api.core.auth import CurrentUser, get_current_user, get_current_user_id, get_user_client


class MockData:
    data = [
        {
            "id": "tx-1",
            "description": "Unknown merchant",
            "amount": -500.0,
            "category": "Uncategorized",
            "suggested_category": "Shopping",
            "confidence_score": 0.72,
            "transaction_date": "2026-01-15T00:00:00Z",
            "merchant_name": "Unknown Merchant",
            "payment_method": "UPI",
            "type": "debit",
            "created_at": "2026-01-15T00:00:00Z",
        }
    ]


class MockTable:
    def __init__(self):
        self._data = MockData()
    def select(self, *args): return self
    def eq(self, *args): return self
    def order(self, *args, **kwargs): return self
    def limit(self, *args): return self
    def execute(self): return self._data


class MockClient:
    def __init__(self):
        self.auth = type("auth", (), {
            "get_user": lambda self: type("r", (), {
                "user": type("u", (), {"id": "user-1"})()
            })()
        })()
    def table(self, name):
        return MockTable()


@pytest.fixture
def client():
    app.dependency_overrides[get_user_client] = lambda: MockClient()
    app.dependency_overrides[get_current_user_id] = lambda: "user-1"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="user-1", email=None)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_uncategorized_endpoint_exists(client):
    resp = client.get(
        "/api/v1/accounts/transactions/uncategorized",
        headers={"Authorization": "Bearer fake-token"},
    )
    assert resp.status_code == 200


def test_uncategorized_returns_list(client):
    resp = client.get(
        "/api/v1/accounts/transactions/uncategorized",
        headers={"Authorization": "Bearer fake-token"},
    )
    data = resp.json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_uncategorized_includes_suggested_category(client):
    resp = client.get(
        "/api/v1/accounts/transactions/uncategorized",
        headers={"Authorization": "Bearer fake-token"},
    )
    items = resp.json()["items"]
    assert len(items) > 0
    assert "suggested_category" in items[0]
    assert "confidence_score" in items[0]
