"""Shared helpers for tests that hit a running local Supabase stack.

These tests require:

    * `supabase start` running (default ports — 54321 API, 54322 Postgres).
    * The migration chain applied (`supabase db reset`).

The local stack ships with well-known anon / service-role JWT secrets
(see `supabase status -o json`). When the stack is not available these
helpers raise an OSError; tests should call ``require_local_stack()`` in
their module-level fixture so unavailability becomes a skip-with-reason
rather than a confusing connection refused.
"""

from __future__ import annotations

import os
import socket
import uuid
from contextlib import closing
from dataclasses import dataclass
from typing import Any

# Default ports + keys hard-coded by `supabase start`. They are NOT
# secrets — they are baked into the supabase CLI's local-dev defaults
# and are identical on every developer machine. Recording them here
# avoids a runtime `supabase status` shell-out per test.
LOCAL_API_URL: str = os.environ.get("SUPABASE_LOCAL_URL", "http://127.0.0.1:54321")
LOCAL_DB_HOST: str = "127.0.0.1"
LOCAL_DB_PORT: int = 54322

LOCAL_ANON_KEY: str = os.environ.get(
    "SUPABASE_LOCAL_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9."
    "CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0",
)
LOCAL_SERVICE_KEY: str = os.environ.get(
    "SUPABASE_LOCAL_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
    "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU",
)


def stack_available() -> bool:
    """Check whether the local supabase Postgres port accepts a connection."""
    try:
        with closing(socket.create_connection((LOCAL_DB_HOST, LOCAL_DB_PORT), timeout=1.0)):
            return True
    except OSError:
        return False


@dataclass(frozen=True)
class TestUser:
    """A throwaway auth.users row created via the admin API.

    The id is a real UUID present in ``auth.users`` — RLS policies
    keyed on ``auth.uid() = user_id`` will see the value when the
    JWT is set on the client (see ``user_scoped_client``).
    """

    user_id: str
    access_token: str
    email: str


def make_service_client() -> Any:
    from supabase import create_client

    return create_client(LOCAL_API_URL, LOCAL_SERVICE_KEY)


def make_anon_client() -> Any:
    from supabase import create_client

    return create_client(LOCAL_API_URL, LOCAL_ANON_KEY)


def create_test_user(*, prefix: str = "scale-test") -> TestUser:
    """Create an auth.users row + sign in to mint a JWT.

    Returns the access_token so the caller can build a user-scoped
    supabase client whose JWT carries the correct ``sub`` claim for
    RLS evaluation. The supabase admin API does NOT return an access
    token directly, so we provision the user with a known password
    and then sign in with it.
    """
    from supabase import create_client

    service = make_service_client()
    email = f"{prefix}-{uuid.uuid4().hex[:8]}@scale.test"
    password = uuid.uuid4().hex
    created = service.auth.admin.create_user({"email": email, "password": password, "email_confirm": True})
    assert created.user is not None
    user_id = created.user.id

    anon = create_client(LOCAL_API_URL, LOCAL_ANON_KEY)
    session = anon.auth.sign_in_with_password({"email": email, "password": password})
    assert session.session is not None, "sign_in returned no session"
    return TestUser(user_id=user_id, access_token=session.session.access_token, email=email)


def user_scoped_client(user: TestUser) -> Any:
    """Return a supabase-py client whose Authorization header carries
    the user's JWT, so `auth.uid()` evaluates correctly inside RLS
    and SECURITY DEFINER functions that read it.
    """
    from supabase import create_client

    client = create_client(LOCAL_API_URL, LOCAL_ANON_KEY)
    client.postgrest.auth(user.access_token)
    return client


def cleanup_user(user_id: str) -> None:
    """Hard-delete an auth.users row. Cascades clean up tenant rows
    via the existing ON DELETE CASCADE FKs.
    """
    try:
        make_service_client().auth.admin.delete_user(user_id)
    except Exception:  # noqa: BLE001 — cleanup is best-effort
        pass
