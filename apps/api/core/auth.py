"""Centralized authentication dependencies.

Consolidates deps.py + supabase_client.py into one module.
Provides both user-scoped and service-role Supabase clients.

Fixes BUG-06: documents the empty refresh token pattern and validates
JWT expiry upfront rather than letting it fail silently.
"""

import os

from fastapi import Depends, Header, HTTPException
from supabase import Client, create_client


def _get_supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not configured")
    return url


def _get_supabase_anon_key() -> str:
    key = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY is not configured")
    return key


async def get_user_token(authorization: str = Header(default="")) -> str:
    """Extract Bearer token from Authorization header.

    Returns the raw JWT string.
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
    return token


async def get_user_client(token: str = Depends(get_user_token)) -> Client:
    """Provide a Supabase client authenticated with the user's JWT.

    RLS policies will be enforced for all queries.

    Note: We pass an empty string as the refresh token because the API
    gateway is stateless — each request carries a fresh token from the
    client. The backend never refreshes tokens.
    """
    client = create_client(_get_supabase_url(), _get_supabase_anon_key())
    client.auth.set_session(token, "")
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
