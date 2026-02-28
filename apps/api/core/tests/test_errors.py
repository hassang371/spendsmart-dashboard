"""Tests for RFC 7807 error handling."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.errors import (
    AppError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    register_error_handlers,
)


@pytest.fixture
def error_app():
    """Create a test app with error handlers registered."""
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/test/not-found")
    async def raise_not_found():
        raise NotFoundError("Transaction xyz not found")

    @app.get("/test/validation")
    async def raise_validation():
        raise ValidationError("Invalid amount")

    @app.get("/test/auth")
    async def raise_auth():
        raise AuthenticationError()

    @app.get("/test/unhandled")
    async def raise_unhandled():
        raise RuntimeError("Unexpected crash")

    return app


@pytest.fixture
def client(error_app):
    return TestClient(error_app, raise_server_exceptions=False)


class TestRFC7807ErrorFormat:
    """All errors should return RFC 7807 Problem Details format."""

    def test_not_found_returns_rfc7807(self, client):
        response = client.get("/test/not-found")
        assert response.status_code == 404
        body = response.json()
        assert body["type"] == "about:blank"
        assert body["title"] == "Not Found"
        assert body["status"] == 404
        assert body["detail"] == "Transaction xyz not found"
        assert body["instance"] == "/test/not-found"

    def test_validation_error_returns_rfc7807(self, client):
        response = client.get("/test/validation")
        assert response.status_code == 422
        body = response.json()
        assert body["title"] == "Unprocessable Entity"
        assert body["detail"] == "Invalid amount"

    def test_auth_error_returns_rfc7807(self, client):
        response = client.get("/test/auth")
        assert response.status_code == 401
        body = response.json()
        assert body["title"] == "Unauthorized"

    def test_unhandled_error_returns_rfc7807(self, client):
        response = client.get("/test/unhandled")
        assert response.status_code == 500
        body = response.json()
        assert body["title"] == "Internal Server Error"
        assert body["detail"] == "An unexpected error occurred"
