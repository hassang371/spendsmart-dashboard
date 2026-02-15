"""Tests for the health endpoint."""
from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_health_returns_200():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_returns_status_ok():
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "healthy"


def test_health_returns_engine_versions():
    response = client.get("/api/v1/health")
    data = response.json()
    assert "engines" in data
    assert "ingestion" in data["engines"]
    assert "forecasting" in data["engines"]
