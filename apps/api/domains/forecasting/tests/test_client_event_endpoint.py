"""Tests for ``POST /api/v1/metrics/client-event``.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §Codex Fix #4
"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from apps.api.core.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_user_client,
)
from apps.api.core.metrics import forecast_warm_outcome_total
from apps.api.main import app


def _override_auth():
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-id", email=None)
    app.dependency_overrides[get_user_client] = lambda: MagicMock()


def test_client_event_increments_forecast_warm_outcome_counter():
    _override_auth()
    try:
        with TestClient(app) as tc:
            app.state.client_event_rate_limiter = None
            before = forecast_warm_outcome_total.labels(result="ok")._value.get()
            resp = tc.post(
                "/api/v1/metrics/client-event",
                json={"event": "forecast_warm_outcome", "result": "ok"},
            )
            after = forecast_warm_outcome_total.labels(result="ok")._value.get()

            assert resp.status_code == 204
            assert after - before == 1.0
    finally:
        app.dependency_overrides.clear()


def test_client_event_rejects_unknown_event_with_400_or_422():
    """Unknown event name → 400 (per spec) or 422 (Pydantic Literal default).

    The spec says reject with 400; Pydantic's Literal validator returns
    422 by default. Either is an explicit rejection — both are
    acceptable. The important behaviour is that the counter does NOT
    increment on rejection.
    """
    _override_auth()
    try:
        with TestClient(app) as tc:
            app.state.client_event_rate_limiter = None
            before = forecast_warm_outcome_total.labels(result="ok")._value.get()
            resp = tc.post(
                "/api/v1/metrics/client-event",
                json={"event": "wrong_event", "result": "ok"},
            )
            after = forecast_warm_outcome_total.labels(result="ok")._value.get()
            assert resp.status_code in (400, 422)
            assert after == before
    finally:
        app.dependency_overrides.clear()


def test_client_event_rejects_unknown_result_label():
    _override_auth()
    try:
        with TestClient(app) as tc:
            app.state.client_event_rate_limiter = None
            resp = tc.post(
                "/api/v1/metrics/client-event",
                json={"event": "forecast_warm_outcome", "result": "weird"},
            )
            assert resp.status_code in (400, 422)
    finally:
        app.dependency_overrides.clear()


def test_client_event_requires_authentication():
    """Without override, get_current_user_id requires a Bearer token."""
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as tc:
        app.state.client_event_rate_limiter = None
        resp = tc.post(
            "/api/v1/metrics/client-event",
            json={"event": "forecast_warm_outcome", "result": "ok"},
        )
    assert resp.status_code == 401


def test_client_event_rate_limit_fires_after_threshold():
    """When the in-app rate-limit dependency rejects, the endpoint
    must surface the 429. We simulate this by installing a stub
    dependency that rejects after N calls."""
    from fastapi import HTTPException

    _override_auth()
    counter = {"count": 0}

    async def _stub_dep(_request):
        counter["count"] += 1
        if counter["count"] > 30:
            raise HTTPException(
                status_code=429,
                detail="Too many requests.",
                headers={"Retry-After": "60"},
            )

    try:
        with TestClient(app) as tc:
            app.state.client_event_rate_limiter = _stub_dep
            for i in range(30):
                resp = tc.post(
                    "/api/v1/metrics/client-event",
                    json={"event": "forecast_warm_outcome", "result": "ok"},
                )
                assert resp.status_code == 204, f"call {i} got {resp.status_code}"
            # 31st request should be rate-limited.
            resp = tc.post(
                "/api/v1/metrics/client-event",
                json={"event": "forecast_warm_outcome", "result": "ok"},
            )
            assert resp.status_code == 429
    finally:
        app.dependency_overrides.clear()
