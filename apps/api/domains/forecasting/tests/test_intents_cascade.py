"""Two-level cascade contract test — LLD 010 §Testing Strategy.

Asserts:
    auth.users  ─CASCADE→  user_intents  ─CASCADE→  scheduled_cashflows
                                                    (where source='intent')

Hard-deleting an auth.users row must remove the user's user_intents
rows AND the bridged scheduled_cashflows rows.

This test is SKIPPED when no Supabase local instance is reachable. The
master plan defers migration apply to Stage 10, so unless the developer
has a local Supabase up and migrations applied, the assertion cannot be
exercised.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md
      §Testing Strategy → Contract Tests → "Two-level cascade"
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_SERVICE_KEY"),
    reason="Requires running Supabase local instance with LLD 010 migrations applied",
)


def test_two_level_cascade_auth_user_to_scheduled_cashflows():
    """SKIP-stub. When migrations are applied (Stage 10), this test
    seeds one user + one dated intent + one LIFE_EVENT, deletes the
    auth.users row, and asserts both tables show zero rows for the
    deleted user.

    The full implementation lands once Stage 10 confirms migrations
    apply cleanly. Today the test is a placeholder skip stub so the
    contract is recorded in the test corpus.
    """
    pytest.skip("Migration apply deferred to Stage 10 per master plan")
