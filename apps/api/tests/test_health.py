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
    assert data["status"] in {"healthy", "degraded"}


def test_health_returns_engine_versions():
    """Readiness probe should report service health."""
    response = client.get("/api/v1/health/ready")
    data = response.json()
    assert "services" in data
    assert "api" in data["services"]
    assert "redis" in data["services"]
