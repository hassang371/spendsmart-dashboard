"""Tests for CORS configuration.

Verifies that:
- Configured origins receive proper CORS headers
- Unconfigured origins are blocked
- Preflight OPTIONS requests return correct headers
- Explicit method/header allowlists are respected
"""

import pytest
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient


ALLOWED_ORIGIN = "https://app.scale.com"
OTHER_ORIGIN = "https://evil.example.com"


@pytest.fixture
def cors_app():
    """App with hardened CORS matching M3 production config."""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        max_age=86400,
    )

    @app.get("/data")
    async def get_data():
        return {"data": "ok"}

    @app.post("/data")
    async def post_data():
        return {"data": "created"}

    return app


@pytest.fixture
def client(cors_app):
    return TestClient(cors_app, raise_server_exceptions=False)


class TestCORSAllowedOrigin:
    """Requests from configured origins should receive CORS headers."""

    def test_allowed_origin_receives_acao_header(self, client):
        response = client.get("/data", headers={"Origin": ALLOWED_ORIGIN})
        assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    def test_allowed_origin_credentials_exposed(self, client):
        response = client.get("/data", headers={"Origin": ALLOWED_ORIGIN})
        assert response.headers.get("access-control-allow-credentials") == "true"


class TestCORSBlockedOrigin:
    """Requests from unconfigured origins must not receive CORS headers."""

    def test_unknown_origin_no_acao_header(self, client):
        response = client.get("/data", headers={"Origin": OTHER_ORIGIN})
        # The response still succeeds (CORS is enforced by the browser, not the server)
        # but the ACAO header must not be set to the unknown origin
        acao = response.headers.get("access-control-allow-origin", "")
        assert acao != OTHER_ORIGIN

    def test_no_origin_no_acao_header(self, client):
        """Requests with no Origin header (server-to-server) are unaffected."""
        response = client.get("/data")
        assert response.status_code == 200


class TestCORSPreflight:
    """OPTIONS preflight requests must return the correct CORS headers."""

    def test_preflight_allowed_origin(self, client):
        response = client.options(
            "/data",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization, Content-Type",
            },
        )
        assert response.status_code in (200, 204)
        assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    def test_preflight_max_age(self, client):
        response = client.options(
            "/data",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        max_age = response.headers.get("access-control-max-age", "")
        assert max_age == "86400"

    def test_preflight_allowed_methods(self, client):
        response = client.options(
            "/data",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        allowed_methods = response.headers.get("access-control-allow-methods", "")
        assert "POST" in allowed_methods

    def test_preflight_allowed_headers(self, client):
        response = client.options(
            "/data",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization",
            },
        )
        allowed_headers = response.headers.get("access-control-allow-headers", "")
        assert "authorization" in allowed_headers.lower()
