"""Tests for auth token expiry validation.

Verifies that expired JWTs are rejected with 401 instead of relying solely
on Supabase to catch them later.
"""

import asyncio
import time
import base64
import json
import pytest
from fastapi import HTTPException

from apps.api.core.auth import _decode_jwt_payload, get_user_token


def _make_dummy_jwt(payload_dict: dict) -> str:
    """Helper to create a structurally valid JWT with specific claims."""
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').decode().rstrip("=")
    payload_bytes = json.dumps(payload_dict).encode()
    payload = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
    signature = "dummy_signature"
    return f"{header}.{payload}.{signature}"


class TestJWTDecoder:
    """Tests for the _decode_jwt_payload function."""

    def test_valid_jwt_decodes(self):
        token = _make_dummy_jwt({"exp": 12345, "sub": "user-123"})
        payload = _decode_jwt_payload(token)
        assert payload["exp"] == 12345
        assert payload["sub"] == "user-123"

    def test_malformed_jwt_raises_value_error(self):
        with pytest.raises(ValueError):
            _decode_jwt_payload("not.a.token")

    def test_invalid_base64_raises_value_error(self):
        token = "header.invalid_base64!.signature"
        with pytest.raises(ValueError):
            _decode_jwt_payload(token)


class TestGetUserToken:
    """Tests for the Dependency extracting and pre-validating the token."""

    def test_missing_header_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_user_token(""))
        assert exc.value.status_code == 401
        assert "Missing" in exc.value.detail

    def test_invalid_scheme_raises_401(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_user_token("Basic dXNlcjpwYXNz"))
        assert exc.value.status_code == 401
        assert "Bearer" in exc.value.detail

    def test_valid_unexpired_token_returns_token(self):
        # Expires 1 hour from now
        future_exp = int(time.time()) + 3600
        token = _make_dummy_jwt({"exp": future_exp, "sub": "user-1"})

        result = asyncio.run(get_user_token(f"Bearer {token}"))
        assert result == token

    def test_expired_token_raises_401(self):
        # Expired 1 hour ago
        past_exp = int(time.time()) - 3600
        token = _make_dummy_jwt({"exp": past_exp, "sub": "user-1"})

        with pytest.raises(HTTPException) as exc:
            asyncio.run(get_user_token(f"Bearer {token}"))

        assert exc.value.status_code == 401
        assert "expired" in exc.value.detail.lower()

    def test_token_without_exp_claim_passes_preflight(self):
        # If no exp claim is present, we defer validation to Supabase
        token = _make_dummy_jwt({"sub": "user-1"})
        result = asyncio.run(get_user_token(f"Bearer {token}"))
        assert result == token
