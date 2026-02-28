"""Supabase client factory for the API Gateway.

Creates per-request Supabase clients using the caller's JWT
so that Row-Level Security is enforced on every query.
"""
import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get(
    "NEXT_PUBLIC_SUPABASE_ANON_KEY"
)


def get_supabase_client(access_token: str | None = None) -> Client:
    """
    Create a Supabase client.

    If an access_token (user JWT) is provided, the client will make
    requests on behalf of that user — RLS policies will apply.
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase environment variables are not configured")

    client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    if access_token:
        # Override the session so PostgREST uses this user's JWT
        client.auth.set_session(access_token, "")

    return client
