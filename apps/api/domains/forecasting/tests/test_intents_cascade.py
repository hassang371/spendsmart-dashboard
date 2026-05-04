"""Two-level cascade contract test — LLD 010 §Testing Strategy.

Asserts:
    auth.users  ─CASCADE→  user_intents  ─CASCADE→  scheduled_cashflows
                                                    (where source='intent')

Hard-deleting an auth.users row must remove the user's user_intents
rows AND the bridged scheduled_cashflows rows.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md
      §Testing Strategy → Contract Tests → "Two-level cascade"
"""

from __future__ import annotations

import pytest

from apps.api.domains.forecasting.tests._supabase_local import (
    cleanup_user,
    create_test_user,
    make_service_client,
    stack_available,
)

pytestmark = pytest.mark.skipif(
    not stack_available(),
    reason="Requires running local supabase stack with LLD 010 migrations applied.",
)


def test_two_level_cascade_auth_user_to_scheduled_cashflows():
    """Deleting auth.users cascades through user_intents to scheduled_cashflows."""
    user = create_test_user(prefix="cascade")
    service = make_service_client()
    cleanup_needed = True
    try:
        # 1. Seed one dated user_intent.
        intent = (
            service.table("user_intents")
            .insert(
                {
                    "user_id": user.user_id,
                    "intent_type": "planned_large_expense",
                    "amount": 50000,
                    "category_bucket": "other",
                    "start_date": "2026-06-01",
                    "confidence": "high",
                    "is_recurring": False,
                }
            )
            .execute()
        )
        assert len(intent.data) == 1
        intent_id = intent.data[0]["id"]

        # 2. Seed the bridged scheduled_cashflows row (source='intent').
        bridge = (
            service.table("scheduled_cashflows")
            .insert(
                {
                    "user_id": user.user_id,
                    "amount": 50000,
                    "category_bucket": "other",
                    "rrule_freq": "monthly",
                    "next_occurrence": "2026-06-01",
                    "confidence": 0.9,
                    "source": "intent",
                    "source_rule_id": intent_id,
                }
            )
            .execute()
        )
        assert len(bridge.data) == 1

        # Sanity: both rows exist for this user.
        intents_pre = service.table("user_intents").select("id", count="exact").eq("user_id", user.user_id).execute()
        cashflows_pre = (
            service.table("scheduled_cashflows").select("id", count="exact").eq("user_id", user.user_id).execute()
        )
        assert intents_pre.count == 1
        assert cashflows_pre.count == 1

        # 3. Hard-delete the auth.users row.
        service.auth.admin.delete_user(user.user_id)
        cleanup_needed = False  # already deleted

        # 4. Both descendant tables must be empty for that user.
        intents_post = service.table("user_intents").select("id", count="exact").eq("user_id", user.user_id).execute()
        cashflows_post = (
            service.table("scheduled_cashflows").select("id", count="exact").eq("user_id", user.user_id).execute()
        )
        assert intents_post.count == 0, f"user_intents did not cascade-delete: {intents_post.count} rows remain"
        assert (
            cashflows_post.count == 0
        ), f"scheduled_cashflows did not cascade-delete: {cashflows_post.count} rows remain"
    finally:
        if cleanup_needed:
            cleanup_user(user.user_id)
