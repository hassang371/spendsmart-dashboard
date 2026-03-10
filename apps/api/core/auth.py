"""Centralized authentication dependencies.

Consolidates deps.py + supabase_client.py into one module.
Provides both user-scoped and service-role Supabase clients.

Fixes BUG-06: documents the empty refresh token pattern and validates
JWT expiry upfront rather than letting it fail silently.

M3: Adds JWT expiry check via base64 decode of the payload claim.
The signature is NOT verified here (Supabase handles that); we only
check the 'exp' claim to return a clear 401 on expired tokens.
"""

import os
import json
import time
import base64
import structlog
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException
from supabase import Client, create_client

from apps.api.core.config import settings

logger = structlog.get_logger()


def _get_supabase_url() -> str:
    # Use settings singleton (reads .env via Pydantic Settings)
    if settings and settings.SUPABASE_URL:
        return settings.SUPABASE_URL
    # Fallback to direct env lookup
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not configured")
    return url


def _get_supabase_anon_key() -> str:
    # Use settings singleton (reads .env via Pydantic Settings)
    if settings and settings.SUPABASE_ANON_KEY:
        return settings.SUPABASE_ANON_KEY
    # Fallback to direct env lookup
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get(
        "NEXT_PUBLIC_SUPABASE_ANON_KEY"
    )
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY is not configured")
    return key


def _decode_jwt_payload(token: str) -> dict:
    """Decode JWT payload without verifying the signature.

    Used only for pre-flight checks (e.g. expiry). Supabase performs
    full cryptographic verification when the token is used in a query.

    Raises ValueError if the token is structurally malformed.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Not a valid JWT structure")
        # Base64url decode (add padding if necessary)
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception as exc:
        raise ValueError(f"Failed to decode JWT payload: {exc}") from exc


async def get_user_token(authorization: str = Header(default="")) -> str:
    """Extract and pre-validate Bearer token from Authorization header.

    Checks:
    1. Header format is "Bearer <token>"
    2. Token is structurally a JWT
    3. Token has not expired (exp claim)

    Returns the raw JWT string for use with Supabase client.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
        )

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
        )

    # Pre-flight expiry check (full verification delegated to Supabase)
    try:
        payload = _decode_jwt_payload(token)
        exp = payload.get("exp")
        CLOCK_SKEW_SECONDS = 30  # Tolerate up to 30s of clock drift
        if exp is not None:
            try:
                if isinstance(exp, (int, float)):
                    exp_ts = int(exp)
                elif isinstance(exp, str):
                    exp_ts = int(exp)
                else:
                    raise ValueError("malformed exp claim type")
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token: malformed exp claim",
                )

            if time.time() > (exp_ts + CLOCK_SKEW_SECONDS):
                logger.warning("jwt_expired", exp=exp)
                raise HTTPException(
                    status_code=401,
                    detail="Token has expired. Please sign in again.",
                )
    except HTTPException:
        raise
    except ValueError:
        # Malformed JWT — let Supabase return the definitive error
        logger.warning("jwt_malformed_payload")

    return token


@dataclass
class CurrentUser:
    id: str
    email: Optional[str]


async def get_current_user(token: str = Depends(get_user_token)) -> CurrentUser:
    """Extract user identity from JWT via Supabase Auth.

    This ensures the token is cryptographically verified against Supabase
    before trusting the 'sub' and 'email' claims, preventing forged tokens
    on endpoints that don't pass through RLS.
    """
    from apps.api.core.config import settings
    from supabase import create_client

    try:
        # Create a client instance with the anon key and set the session token
        client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)

        # Call the Supabase auth API to verify the token signature
        user_response = client.auth.get_user(token)

        if not user_response or not user_response.user:
            raise ValueError("Token rejected by auth server")

        user = user_response.user
        return CurrentUser(id=user.id, email=user.email)

    except HTTPException:
        raise
    except Exception as e:
        logger.warning("auth_verification_failed", error=str(e))
        raise HTTPException(
            status_code=401, detail="Invalid or expired authentication token"
        )


async def get_current_user_id(user: CurrentUser = Depends(get_current_user)) -> str:
    """Convenience dependency: return just the user UUID."""
    return user.id


async def get_user_client(token: str = Depends(get_user_token)) -> Client:
    """Provide a Supabase client authenticated with the user's JWT.

    Uses postgrest.auth() instead of auth.set_session() to avoid the
    internal get_user() network call that set_session() triggers.
    RLS policies are still fully enforced — Supabase verifies the JWT
    on every PostgREST request server-side.
    """
    client = create_client(_get_supabase_url(), _get_supabase_anon_key())
    client.postgrest.auth(token)
    return client


def get_service_client() -> Client:
    """Provide a service-role Supabase client (bypasses RLS).

    Used by Celery workers to update training_jobs status.
    """
    url = _get_supabase_url()
    service_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not service_key:
        raise RuntimeError("SUPABASE_SERVICE_KEY is not configured")
    return create_client(url, service_key)
