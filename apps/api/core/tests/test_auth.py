"""Tests for centralized auth dependency (core/auth.py).

Covers:
- Missing / malformed Authorization header → 401
- Expired JWT (exp claim in the past) → 401
- Valid-looking JWT passes through (Supabase does full verification)
- get_user_token extracts token correctly
"""

import base64
import json
import time

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from apps.api.core.auth import _decode_jwt_payload, get_user_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_jwt(payload: dict) -> str:
    """Build a minimal JWT (unsigned) for testing."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()

    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()

    # Fake signature — auth.py does NOT verify signatures
    sig = base64.urlsafe_b64encode(b"fakesig").rstrip(b"=").decode()
    return f"{header}.{payload_b64}.{sig}"


def _valid_token(exp_offset: int = 3600) -> str:
    """Return a token that expires in `exp_offset` seconds (default: 1h)."""
    return _make_jwt({"sub": "user-123", "exp": int(time.time()) + exp_offset})


def _expired_token() -> str:
    """Return a token that expired 1 hour ago."""
    return _make_jwt({"sub": "user-123", "exp": int(time.time()) - 3600})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_app():
    """Minimal FastAPI app that uses get_user_token."""
    app = FastAPI()

    @app.get("/protected")
    async def protected(token: str = Depends(get_user_token)):
        return {"token_len": len(token)}

    return app


@pytest.fixture
def client(auth_app):
    return TestClient(auth_app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Unit: _decode_jwt_payload
# ---------------------------------------------------------------------------


class TestDecodeJwtPayload:
    def test_decodes_valid_payload(self):
        token = _make_jwt({"sub": "user-1", "exp": 9999999999})
        payload = _decode_jwt_payload(token)
        assert payload["sub"] == "user-1"
        assert payload["exp"] == 9999999999

    def test_raises_on_non_jwt_string(self):
        with pytest.raises(ValueError):
            _decode_jwt_payload("not-a-jwt")

    def test_raises_on_two_part_token(self):
        with pytest.raises(ValueError):
            _decode_jwt_payload("header.payload")

    def test_handles_missing_padding(self):
        """Base64url strings without padding must still decode correctly."""
        token = _make_jwt({"x": "y"})
        payload = _decode_jwt_payload(token)
        assert payload["x"] == "y"


# ---------------------------------------------------------------------------
# Integration: get_user_token dependency
# ---------------------------------------------------------------------------


class TestGetUserToken:
    def test_missing_authorization_header_returns_401(self, client):
        response = client.get("/protected")
        assert response.status_code == 401

    def test_non_bearer_scheme_returns_401(self, client):
        response = client.get("/protected", headers={"Authorization": "Basic abc123"})
        assert response.status_code == 401

    def test_empty_bearer_returns_401(self, client):
        response = client.get("/protected", headers={"Authorization": "Bearer "})
        assert response.status_code == 401

    def test_expired_token_returns_401(self, client):
        token = _expired_token()
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    def test_valid_token_passes_through(self, client):
        """A non-expired token should not be rejected by the pre-flight check."""
        token = _valid_token()
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        # Should reach the endpoint (200), not be rejected (401)
        assert response.status_code == 200

    def test_malformed_jwt_passes_through(self, client):
        """A structurally invalid JWT is allowed through for Supabase to reject."""
        response = client.get("/protected", headers={"Authorization": "Bearer not.a.realJWT"})
        # The pre-flight decoding fails gracefully; Supabase will reject it later.
        # The pre-flight should NOT raise a 401 for malformed payloads.
        # (The endpoint itself might fail at the Supabase layer, but that's outside this test.)
        assert response.status_code == 200  # auth.py passes it through

    def test_malformed_exp_claim_dict_returns_401(self, client):
        """If `exp` is structurally valid JSON but not a number/string, it shouldn't crash."""
        token = _make_jwt({"sub": "user-123", "exp": {"unknown": "format"}})
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "malformed exp claim" in response.json()["detail"].lower()

    def test_malformed_exp_claim_list_returns_401(self, client):
        """If `exp` is structurally valid JSON but it is a list, it shouldn't crash."""
        token = _make_jwt({"sub": "user-123", "exp": [1, 2, 3]})
        response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert "malformed exp claim" in response.json()["detail"].lower()
