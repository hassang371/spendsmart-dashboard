"""Tests for BUG-002: safe-to-spend must only return the authenticated user's data.

Each test verifies that the `user_id` filter is applied to the transactions
query so that cross-tenant leakage cannot occur even if RLS has a gap.
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_client():
    """Supabase client mock — chains .table().select().eq().eq().gte()...execute()."""
    client = MagicMock()
    # Build a chainable query mock
    query = MagicMock()
    query.select.return_value = query
    query.eq.return_value = query
    query.gte.return_value = query
    query.order.return_value = query
    query.limit.return_value = query
    client.table.return_value = query
    return client, query


def _make_rows(user_ids: list[str]) -> list[dict]:
    return [
        {
            "transaction_date": "2025-10-01",
            "amount": -50.0 * i,
            "status": "cleared",
            # Simulated DB row that includes user_id (would not be present
            # if the select projection were strict, but useful for testing)
            "user_id": uid,
        }
        for i, uid in enumerate(user_ids, start=1)
    ]


def test_safe_to_spend_applies_user_id_filter(mock_client):
    """BUG-002: The query MUST call .eq('user_id', user_id) before fetching rows."""
    client, query = mock_client
    user_id = "user-abc-123"

    # Simulate 10 transactions belonging only to user-abc-123
    query.execute.return_value.data = _make_rows([user_id] * 10)

    with (
        patch(
            "apps.api.domains.forecasting.router.get_current_user_id",
            return_value=user_id,
        ),
        patch(
            "apps.api.domains.forecasting.router.get_user_client",
            return_value=client,
        ),
    ):
        from apps.api.domains.forecasting.router import safe_to_spend

        # Call the function directly (bypassing FastAPI DI)
        asyncio.run(safe_to_spend(user_id=user_id, client=client))

    # The .eq() chain must have been called with user_id
    eq_calls = [str(c) for c in query.eq.call_args_list]
    user_id_filter_applied = any("user_id" in c and user_id in c for c in eq_calls)
    assert user_id_filter_applied, (
        "BUG-002: .eq('user_id', user_id) was NOT called in the safe-to-spend " f"query. eq calls were: {eq_calls}"
    )


def test_safe_to_spend_no_other_user_rows_returned(mock_client):
    """BUG-002: Cross-tenant rows must never appear in safe-to-spend result."""
    client, query = mock_client
    user_id = "user-tenant-A"
    other_user_id = "user-tenant-B"

    # Only return rows for the authenticated user (the DB should enforce this
    # via RLS + explicit filter — this verifies filter was applied)
    query.execute.return_value.data = _make_rows([user_id] * 5)

    with (
        patch(
            "apps.api.domains.forecasting.router.get_current_user_id",
            return_value=user_id,
        ),
        patch(
            "apps.api.domains.forecasting.router.get_user_client",
            return_value=client,
        ),
    ):
        from apps.api.domains.forecasting.router import safe_to_spend

        result = asyncio.run(safe_to_spend(user_id=user_id, client=client))

    # Result must be a dict with expected keys (not a cross-tenant data dump)
    assert "safe_amount" in result
    assert "currency" in result

    # Verify .eq was called with the correct user_id (not other_user_id)
    all_eq_args = [call.args for call in query.eq.call_args_list]
    assert (
        "user_id",
        user_id,
    ) in all_eq_args, f"Expected eq('user_id', '{user_id}') in query chain. Got: {all_eq_args}"
    assert (
        "user_id",
        other_user_id,
    ) not in all_eq_args, "Cross-tenant user_id must not appear in query filter"
