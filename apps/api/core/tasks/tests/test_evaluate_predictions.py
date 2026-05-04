"""Tests for ``evaluate_past_predictions`` (RFC-003 §5).

Covers:

* Pinball-loss math is golden against ``sklearn.metrics.mean_pinball_loss``.
* MAPE math matches the documented formula.
* The lease-based claim query is testable end-to-end against a real
  Postgres (skipped when ``supabase start`` is not available).

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §5
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

# ---------------------------------------------------------------------------
# Pure-math tests (no DB)
# ---------------------------------------------------------------------------


def test_pinball_loss_matches_sklearn():
    """Per-quantile pinball loss matches sklearn within 1e-9."""
    import numpy as np

    pytest.importorskip("sklearn")
    from sklearn.metrics import mean_pinball_loss

    from apps.api.core.tasks.evaluate_predictions import compute_pinball_loss

    rng = np.random.default_rng(0)
    y_true = rng.normal(loc=10_000.0, scale=500.0, size=30)

    quantile_levels = [0.02, 0.10, 0.25, 0.50, 0.75, 0.90, 0.98]
    forecasts: list[dict[str, float]] = []
    for i in range(30):
        median = float(y_true[i] + rng.normal(0, 100))
        forecasts.append(
            {
                "p2": median - 2000,
                "p10": median - 1000,
                "p25": median - 500,
                "p50": median,
                "p75": median + 500,
                "p90": median + 1000,
                "p98": median + 2000,
            }
        )

    losses = compute_pinball_loss(y_true.tolist(), forecasts)
    for q in quantile_levels:
        key = f"p{int(q * 100) if q != 0.02 else 2}"
        # Build the per-quantile prediction vector
        y_pred = [fc[key] for fc in forecasts]
        expected = mean_pinball_loss(y_true, y_pred, alpha=q)
        assert abs(losses[key] - expected) < 1e-9, f"{key} mismatch: got {losses[key]}, expected {expected}"


def test_compute_mape_matches_formula():
    """``compute_mape(y_true, y_pred)`` ≡ mean(abs((y_true - y_pred) / y_true))."""
    from apps.api.core.tasks.evaluate_predictions import compute_mape

    y_true = [100.0, 200.0, 300.0]
    y_pred = [90.0, 220.0, 270.0]
    expected = (abs(0.10) + abs(0.10) + abs(0.10)) / 3.0
    assert abs(compute_mape(y_true, y_pred) - expected) < 1e-9


def test_compute_mape_returns_none_for_zero_truths():
    """Division-by-zero edge case → return ``None`` so the row's ``mape`` stays NULL."""
    from apps.api.core.tasks.evaluate_predictions import compute_mape

    assert compute_mape([0.0, 0.0], [10.0, 20.0]) is None


# ---------------------------------------------------------------------------
# DB-backed tests — skipped when local supabase unavailable
# ---------------------------------------------------------------------------


from apps.api.domains.forecasting.tests._supabase_local import (  # noqa: E402
    cleanup_user,
    create_test_user,
    make_service_client,
    stack_available,
)

_db_skip = pytest.mark.skipif(
    not stack_available(),
    reason="Requires running local supabase stack (run `supabase start`).",
)


def _build_forecast(horizon: int) -> list[dict[str, float]]:
    return [
        {
            "date": (dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat(),
            "p2": 0.0,
            "p10": 0.0,
            "p25": 0.0,
            "p50": 0.0,
            "p75": 0.0,
            "p90": 0.0,
            "p98": 0.0,
        }
        for i in range(horizon)
    ]


def _seed_matured_prediction(
    service,
    *,
    user_id: str,
    horizon_days: int = 7,
    days_in_past: int = 14,
    claimed_at: dt.datetime | None = None,
    lease_expires_at: dt.datetime | None = None,
) -> str:
    """Insert a user_predictions row whose horizon_end is in the past.

    Service-role insert bypasses RLS and the log_user_prediction RPC's
    server-derived ``generated_at`` so we can place the row precisely
    where the lease/claim filter will match.
    """
    pred_id = str(uuid.uuid4())
    generated_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days_in_past)
    horizon_end = (generated_at + dt.timedelta(days=horizon_days)).date().isoformat()
    row: dict = {
        "prediction_id": pred_id,
        "user_id": user_id,
        "generated_at": generated_at.isoformat(),
        "model_type": "tft_hybrid",
        "model_version": "v0.0.0-test",
        "horizon_days": horizon_days,
        "horizon_end": horizon_end,
        "forecast": _build_forecast(horizon_days),
        "insights": {"frozen": True},
        "insights_version": "v1",
        "shown_to_user": True,
    }
    if claimed_at is not None:
        row["claimed_at"] = claimed_at.isoformat()
    if lease_expires_at is not None:
        row["lease_expires_at"] = lease_expires_at.isoformat()
    service.table("user_predictions").insert(row).execute()
    return pred_id


@_db_skip
def test_unclaimed_matured_row_is_evaluated(monkeypatch):
    """Happy path — a matured, unclaimed row is claimed, evaluated, marked.

    With no ``transactions`` rows for the test user, ``_evaluate_row``
    takes the no_data sentinel branch and writes ``evaluated_at = now()``.
    The atomic-claim fallback path (no SECURITY DEFINER helper) is
    exercised because ``claim_predictions_for_evaluation`` is not
    installed locally.
    """
    from apps.api.core.tasks import evaluate_predictions as ep

    user = create_test_user(prefix="lease-happy")
    service = make_service_client()
    monkeypatch.setattr(ep, "get_service_client", make_service_client)
    try:
        pred_id = _seed_matured_prediction(service, user_id=user.user_id)

        result = ep.evaluate_past_predictions()

        assert result["claimed"] >= 1, result
        assert result["succeeded"] >= 1, result

        row = (
            service.table("user_predictions")
            .select("evaluated_at, claimed_at, lease_expires_at, actual_outcomes")
            .eq("prediction_id", pred_id)
            .single()
            .execute()
        )
        assert row.data["evaluated_at"] is not None, row.data
        # After eval, the lease columns are cleared.
        assert row.data["claimed_at"] is None, row.data
        assert row.data["lease_expires_at"] is None, row.data
        assert row.data["actual_outcomes"] == {"note": "no_data"}, row.data
    finally:
        cleanup_user(user.user_id)


@_db_skip
def test_crashed_worker_row_is_reclaimable(monkeypatch):
    """A row with a stale lease (lease_expires_at < now()) is re-claimed.

    Simulates a crashed worker by seeding a row whose ``claimed_at`` is
    set but whose ``lease_expires_at`` is already in the past. The next
    evaluate pass must claim it again and complete the evaluation.
    """
    from apps.api.core.tasks import evaluate_predictions as ep

    user = create_test_user(prefix="lease-stale")
    service = make_service_client()
    monkeypatch.setattr(ep, "get_service_client", make_service_client)
    try:
        now = dt.datetime.now(dt.timezone.utc)
        pred_id = _seed_matured_prediction(
            service,
            user_id=user.user_id,
            claimed_at=now - dt.timedelta(hours=1),
            lease_expires_at=now - dt.timedelta(minutes=30),
        )

        result = ep.evaluate_past_predictions()
        assert result["claimed"] >= 1, result

        row = (
            service.table("user_predictions")
            .select("evaluated_at, claimed_at, lease_expires_at")
            .eq("prediction_id", pred_id)
            .single()
            .execute()
        )
        assert row.data["evaluated_at"] is not None, row.data
        assert row.data["claimed_at"] is None, row.data
    finally:
        cleanup_user(user.user_id)


@_db_skip
def test_active_lease_row_is_skipped(monkeypatch):
    """A row whose lease is still valid is NOT claimed by another pass.

    This proves the OR-clause in the claim filter:
        (claimed_at IS NULL OR lease_expires_at < now())
    correctly skips rows whose lease is in the future.
    """
    from apps.api.core.tasks import evaluate_predictions as ep

    user = create_test_user(prefix="lease-active")
    service = make_service_client()
    monkeypatch.setattr(ep, "get_service_client", make_service_client)
    try:
        now = dt.datetime.now(dt.timezone.utc)
        pred_id = _seed_matured_prediction(
            service,
            user_id=user.user_id,
            claimed_at=now,
            lease_expires_at=now + dt.timedelta(minutes=30),
        )

        # The function should NOT touch this row — its lease is fresh.
        ep.evaluate_past_predictions()

        row = (
            service.table("user_predictions")
            .select("evaluated_at, claimed_at, lease_expires_at")
            .eq("prediction_id", pred_id)
            .single()
            .execute()
        )
        # evaluated_at remains NULL because the row was skipped.
        assert row.data["evaluated_at"] is None, row.data
        # claimed_at unchanged.
        assert row.data["claimed_at"] is not None, row.data
    finally:
        cleanup_user(user.user_id)


@_db_skip
@pytest.mark.skip(
    reason=(
        "True FOR UPDATE SKIP LOCKED concurrency requires two real Postgres "
        "sessions racing. The supabase-py client serialises requests on a "
        "single connection; emulating it from one process is not "
        "deterministic without spinning up a second worker process. "
        "Covered manually via psql."
    )
)
def test_atomic_claim_skips_locked():
    """Two concurrent claim runs return disjoint claim sets (FOR UPDATE SKIP LOCKED)."""
    raise AssertionError("see skip reason")
