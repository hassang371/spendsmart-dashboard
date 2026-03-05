"""Tests for the ingestion domain router — CSV upload flow.

Migrated from apps/api/tests/test_ingestion.py to test the new domain router.
"""

import io
import torch
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.domains.ingestion.router import router
from apps.api.core.auth import get_user_client


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture(autouse=True)
def mock_classifier(monkeypatch):
    """Mock HypCDClassifier to avoid loading the full model."""

    class MockClassifier:
        def predict_batch(self, texts):
            return [("Food", 0.8, torch.zeros(1, 384)) for _ in texts]

    monkeypatch.setattr(
        "apps.api.domains.ingestion.router.get_classifier",
        lambda: MockClassifier(),
        raising=False,
    )


@pytest.fixture
def mock_user_client():
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_client.auth.get_user.return_value = MagicMock(user=mock_user)
    return mock_client


@pytest.fixture
def client(app, mock_user_client):
    app.dependency_overrides[get_user_client] = lambda: mock_user_client
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


CSV_SAMPLE = """Date,Amount,Description,Merchant
2026-01-01,50.00,Coffee,Starbucks
2026-01-02,-120.00,Grocery run,Whole Foods
2026-01-03,15.99,Lunch,Subway
"""


def test_ingest_csv_returns_200(client):
    file = io.BytesIO(CSV_SAMPLE.encode("utf-8"))
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    assert response.status_code == 200


def test_ingest_csv_returns_transactions(client):
    file = io.BytesIO(CSV_SAMPLE.encode("utf-8"))
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    data = response.json()
    assert "transactions" in data
    assert len(data["transactions"]) == 3


def test_ingest_csv_includes_fingerprint(client):
    file = io.BytesIO(CSV_SAMPLE.encode("utf-8"))
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("transactions.csv", file, "text/csv")},
    )
    data = response.json()
    for tx in data["transactions"]:
        assert "fingerprint" in tx
        assert len(tx["fingerprint"]) == 64


def test_ingest_csv_rejects_non_csv(client):
    file = io.BytesIO(b"this is not csv content at all")
    response = client.post(
        "/api/v1/ingest/csv",
        files={"file": ("photo.jpg", file, "image/jpeg")},
    )
    assert response.status_code == 400
