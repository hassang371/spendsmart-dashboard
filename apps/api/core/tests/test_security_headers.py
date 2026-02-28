"""Tests for SecurityHeadersMiddleware and ContentSizeLimitMiddleware.

Verifies that every response carries the required defensive headers and
that oversized request bodies are rejected before reaching domain logic.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.security_headers import SecurityHeadersMiddleware
from apps.api.main import ContentSizeLimitMiddleware


@pytest.fixture
def secure_app():
    """Minimal app with security headers middleware (dev mode)."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, production=False)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


@pytest.fixture
def secure_app_production():
    """Minimal app with security headers middleware (production mode)."""
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware, production=True)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    return app


@pytest.fixture
def client(secure_app):
    return TestClient(secure_app)


@pytest.fixture
def prod_client(secure_app_production):
    return TestClient(secure_app_production)


class TestSecurityHeaders:
    """Every response must carry defensive HTTP headers."""

    def test_x_frame_options_deny(self, client):
        response = client.get("/ping")
        assert response.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options_nosniff(self, client):
        response = client.get("/ping")
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy(self, client):
        response = client.get("/ping")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client):
        response = client.get("/ping")
        policy = response.headers.get("permissions-policy", "")
        assert "geolocation=()" in policy
        assert "camera=()" in policy

    def test_content_security_policy(self, client):
        response = client.get("/ping")
        csp = response.headers.get("content-security-policy", "")
        assert "default-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_server_header_removed(self, client):
        response = client.get("/ping")
        assert "server" not in response.headers

    def test_no_hsts_in_dev_mode(self, client):
        """HSTS must NOT be set in development (breaks local HTTP)."""
        response = client.get("/ping")
        assert "strict-transport-security" not in response.headers

    def test_hsts_present_in_production(self, prod_client):
        """HSTS must be set in production mode."""
        response = prod_client.get("/ping")
        hsts = response.headers.get("strict-transport-security", "")
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts


class TestContentSizeLimitMiddleware:
    """Requests exceeding the size limit must be rejected with 413."""

    @pytest.fixture
    def size_limited_app(self):
        app = FastAPI()
        app.add_middleware(ContentSizeLimitMiddleware, max_bytes=100)

        @app.post("/upload")
        async def upload():
            return {"ok": True}

        return app

    def test_request_under_limit_passes(self, size_limited_app):
        client = TestClient(size_limited_app)
        response = client.post(
            "/upload",
            content=b"x" * 50,
            headers={"content-length": "50"},
        )
        assert response.status_code == 200

    def test_request_over_limit_rejected(self, size_limited_app):
        client = TestClient(size_limited_app)
        response = client.post(
            "/upload",
            content=b"x" * 200,
            headers={"content-length": "200"},
        )
        assert response.status_code == 413
        body = response.json()
        assert body["status"] == 413
        assert "Content Too Large" in body["title"]

    def test_no_content_length_header_passes(self, size_limited_app):
        """Requests without Content-Length header are not blocked."""
        client = TestClient(size_limited_app)
        # TestClient sends transfer-encoding: chunked when no content-length
        response = client.post("/upload", content=b"small")
        assert response.status_code == 200
