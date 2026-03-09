import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from apps.api.main import app


class TestRequestIDMiddleware:
    """Test suite for the RequestIdMiddleware."""
    @pytest.fixture(autouse=True)
    def setup_client(self):
        self.client = TestClient(app)

    def test_response_includes_request_id(self):
        """Verify every response gets an X-Request-ID header generated."""
        response = self.client.get("/api/v1/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 10

    def test_preserves_existing_request_id(self):
        """Verify it preserves an existing X-Request-ID if sent by a client/proxy."""
        custom_id = "custom-req-12345"
        response = self.client.get(
            "/api/v1/health", headers={"X-Request-ID": custom_id}
        )
        assert response.headers["X-Request-ID"] == custom_id


class TestRequestLoggingMiddleware:
    """Test suite for the RequestLoggingMiddleware."""
    # Note: capturing structlog output is tricky without dedicated helpers,
    # but we can at least assert the middleware doesn't break standard flows
    # and the request processes successfully. Deeper log assertions can be
    # added if using a structlog capture fixture.

    def test_request_logging_runs_without_interference(self):
        client = TestClient(app)
        response = client.get("/api/v1/health")
        assert response.status_code == 200

class TestHealthEndpoints:
    """Test suite for liveness and readiness probes."""

    def test_health_liveness_returns_200(self):
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_ready_readiness_returns_200(self):
        client = TestClient(app)
        # Mock the async warmup being complete to test the 200 path
        app.state.classifier_ready = True
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"
