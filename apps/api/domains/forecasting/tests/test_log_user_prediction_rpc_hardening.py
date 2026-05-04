"""RPC trust-boundary hardening tests (Codex pass-2 Fix #5/#6).

Exercises each guard inside ``public.log_user_prediction(payload jsonb)``:

    * Tenant guard — payload ``user_id`` mismatched with ``auth.uid()`` raises
    * NOT NULL guards on ``prediction_id``, ``insights_version``, ``forecast``,
      ``insights``
    * ``horizon_days`` rejected outside [1, 30]
    * ``model_type`` rejected outside ('chronos2','tft_hybrid','ensemble')
    * Server-derived fields — ``generated_at`` and ``horizon_end`` are
      computed inside the function regardless of caller-supplied values
      (caller cannot back-date a prediction)

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §4
"""

from __future__ import annotations

import datetime as dt
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


def _valid_payload(user_id: str, **overrides) -> dict:
    payload = {
        "prediction_id": str(uuid.uuid4()),
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
    payload.update(overrides)
    return payload


def _expect_rpc_error(client, payload: dict, contains: str) -> None:
    """RPC raise paths surface as APIError on the supabase client."""
    with pytest.raises(Exception) as excinfo:
        client.rpc("log_user_prediction", {"payload": payload}).execute()
    assert (
        contains.lower() in str(excinfo.value).lower()
    ), f"expected error containing {contains!r}, got: {excinfo.value!r}"


def test_tenant_guard_rejects_other_user_id():
    user = create_test_user(prefix="rpc-tenant")
    try:
        client = user_scoped_client(user)
        # Build a payload claiming a *different* user_id; the function
        # asserts payload->>'user_id' = auth.uid()::text and raises.
        someone_else = str(uuid.uuid4())
        _expect_rpc_error(
            client,
            _valid_payload(someone_else),
            contains="user_id mismatch",
        )
    finally:
        cleanup_user(user.user_id)


def test_horizon_out_of_range_rejected():
    user = create_test_user(prefix="rpc-horizon")
    try:
        client = user_scoped_client(user)
        _expect_rpc_error(client, _valid_payload(user.user_id, horizon_days=0), contains="horizon_days")
        _expect_rpc_error(client, _valid_payload(user.user_id, horizon_days=31), contains="horizon_days")
    finally:
        cleanup_user(user.user_id)


def test_invalid_model_type_rejected():
    user = create_test_user(prefix="rpc-model")
    try:
        client = user_scoped_client(user)
        _expect_rpc_error(
            client,
            _valid_payload(user.user_id, model_type="not_a_real_model"),
            contains="model_type",
        )
    finally:
        cleanup_user(user.user_id)


def test_missing_required_fields_rejected():
    user = create_test_user(prefix="rpc-required")
    try:
        client = user_scoped_client(user)
        # prediction_id required
        bad = _valid_payload(user.user_id)
        bad.pop("prediction_id")
        _expect_rpc_error(client, bad, contains="prediction_id")

        # insights_version required
        bad = _valid_payload(user.user_id)
        bad.pop("insights_version")
        _expect_rpc_error(client, bad, contains="insights_version")

        # forecast required
        bad = _valid_payload(user.user_id)
        bad.pop("forecast")
        _expect_rpc_error(client, bad, contains="forecast")

        # insights required
        bad = _valid_payload(user.user_id)
        bad.pop("insights")
        _expect_rpc_error(client, bad, contains="insights")
    finally:
        cleanup_user(user.user_id)


def test_server_derives_generated_at_and_horizon_end():
    """Caller-supplied generated_at / horizon_end values are ignored.

    The Codex Fix #5/#6 trust boundary requires that caller-supplied
    timestamps cannot back-date a prediction. The RPC computes
    ``generated_at = now()`` and ``horizon_end = now()::date + horizon_days``
    inside the function regardless of whether the payload mentioned them.
    """
    user = create_test_user(prefix="rpc-server-derived")
    try:
        client = user_scoped_client(user)
        # Caller tries to back-date one year and ask for a horizon_end
        # that does not match horizon_days. Both should be ignored.
        attempted_back_date = "2025-01-01T00:00:00+00:00"
        attempted_horizon_end = "2030-12-31"
        payload = _valid_payload(
            user.user_id,
            horizon_days=14,
            generated_at=attempted_back_date,
            horizon_end=attempted_horizon_end,
        )
        result = client.rpc("log_user_prediction", {"payload": payload}).execute()
        assert result.data is True

        service = make_service_client()
        row = (
            service.table("user_predictions")
            .select("generated_at,horizon_end,horizon_days")
            .eq("user_id", user.user_id)
            .single()
            .execute()
        )
        # generated_at must be near now() — definitely NOT 2025-01-01
        gen_at = dt.datetime.fromisoformat(row.data["generated_at"].replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        assert (now - gen_at).total_seconds() < 60, f"generated_at not server-derived: {gen_at}"

        # horizon_end must equal generated_at::date + horizon_days, NOT 2030
        expected_end = (gen_at.date() + dt.timedelta(days=14)).isoformat()
        assert row.data["horizon_end"] == expected_end, (
            f"horizon_end not server-derived: got {row.data['horizon_end']!r} " f"(expected {expected_end!r})"
        )
        assert row.data["horizon_days"] == 14
    finally:
        cleanup_user(user.user_id)
