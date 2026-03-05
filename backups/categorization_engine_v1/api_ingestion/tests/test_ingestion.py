"""Tests for the CSV ingestion endpoint."""
import io
import torch
import pytest
from types import SimpleNamespace
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.api.core.auth import get_user_client

client = TestClient(app)





@pytest.fixture(autouse=True)
def mock_user_client():
    class MockClient:
        def __init__(self):
            self.auth = SimpleNamespace(
                get_user=lambda: SimpleNamespace(
                    user=SimpleNamespace(id="test-user-id")
                )
            )

    app.dependency_overrides[get_user_client] = lambda: MockClient()
    yield
    app.dependency_overrides.clear()


CSV_SAMPLE = """Date,Amount,Description,Merchant
2026-01-01,50.00,Coffee,Starbucks
2026-01-02,-120.00,Grocery run,Whole Foods
2026-01-03,15.99,Lunch,Subway
"""


def test_ingest_csv_returns_200():
    """Upload a CSV and get a 200 response."""
    file = io.BytesIO(CSV_SAMPLE.encode("utf-8"))
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    assert response.status_code == 200


def test_ingest_csv_returns_transactions():
    """Response should contain a list of parsed transactions."""
    file = io.BytesIO(CSV_SAMPLE.encode("utf-8"))
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    data = response.json()
    assert "transactions" in data
    assert len(data["transactions"]) == 3


def test_ingest_csv_includes_fingerprint():
    """Each transaction should have a fingerprint field."""
    file = io.BytesIO(CSV_SAMPLE.encode("utf-8"))
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    data = response.json()
    for tx in data["transactions"]:
        assert "fingerprint" in tx
        assert len(tx["fingerprint"]) == 64  # SHA256 hex length


def test_ingest_csv_normalizes_columns():
    """Response transactions should have standardized column names."""
    file = io.BytesIO(CSV_SAMPLE.encode("utf-8"))
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    data = response.json()
    tx = data["transactions"][0]
    assert "date" in tx
    assert "amount" in tx
    assert "merchant" in tx


def test_ingest_csv_rejects_non_csv():
    """Uploading a non-CSV file should return 400."""
    file = io.BytesIO(b"this is not csv content at all")
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("photo.jpg", file, "image/jpeg")},
    )
    assert response.status_code == 400
