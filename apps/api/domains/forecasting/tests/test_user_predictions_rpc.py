"""Integration test: log_user_prediction RPC dedup behaviour.

Calls the RPC twice in the same hour bucket for the same user and asserts:
    * first call returns true (row inserted)
    * second call returns false (ON CONFLICT DO NOTHING path)
    * exactly one row exists in user_predictions for that (user_id, hour)

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §4
      docs/bugs/BUG-019-user-predictions-generated-hour-not-immutable.md
"""

from __future__ import annotations

import uuid

import pytest

from apps.api.domains.forecasting.tests._supabase_local import (
    cleanup_user,
    create_test_user,
    make_service_client,
    stack_available,
    user_scoped_client,
)

pytestmark = pytest.mark.skipif(
    not stack_available(),
    reason="Requires running local supabase stack (run `supabase start`).",
)


def _make_payload(user_id: str, *, prediction_id: str | None = None) -> dict:
    """Build a minimal valid payload that satisfies all RPC guards.

    Mirrors the production INSERT shape from
    ``apps/api/domains/forecasting/service.py::_log_prediction``.
    """
    return {
        "prediction_id": prediction_id or str(uuid.uuid4()),
        "user_id": user_id,
        "model_type": "tft_hybrid",
        "model_version": "v0.0.0-test",
        "horizon_days": 7,
        "forecast": [
            {
                "date": "2026-05-05",
                "p2": -1.0,
                "p10": 0.0,
                "p25": 1.0,
                "p50": 2.0,
                "p75": 3.0,
                "p90": 4.0,
                "p98": 5.0,
            }
        ],
        "variable_importance": None,
        "insights": {"frozen": True},
        "insights_version": "v1",
        "shown_to_user": True,
    }


def test_rpc_dedups_within_hour():
    """First RPC call inserts; second call (same user, same hour) returns False."""
    user = create_test_user(prefix="rpc-dedup")
    try:
        client = user_scoped_client(user)
        payload_a = _make_payload(user.user_id)
        first = client.rpc("log_user_prediction", {"payload": payload_a}).execute()
        assert first.data is True, f"first call should insert; got {first.data!r}"

        # Second call with a fresh prediction_id but same user + same UTC
        # hour: the unique expression index on
        # (user_id, date_trunc('hour', generated_at, 'UTC')) collides and
        # ON CONFLICT DO NOTHING returns 0 rows ⇒ RPC returns false.
        payload_b = _make_payload(user.user_id)
        second = client.rpc("log_user_prediction", {"payload": payload_b}).execute()
        assert second.data is False, f"second call should be deduped; got {second.data!r}"

        # And only one row landed.
        service = make_service_client()
        rows = service.table("user_predictions").select("prediction_id").eq("user_id", user.user_id).execute()
        assert len(rows.data) == 1, f"expected 1 row, got {len(rows.data)}: {rows.data!r}"
    finally:
        cleanup_user(user.user_id)
