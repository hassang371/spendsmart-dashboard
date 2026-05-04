"""Router tests for /api/v1/forecast/intents/* — LLD 010.

Exercises the FastAPI surface with a TestClient + mocked IntentsService.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md §API Changes
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from apps.api.core.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_user_client,
)
from apps.api.domains.forecasting.intents_service import IntentsService
from apps.api.domains.forecasting.router import _get_intents_service
from apps.api.domains.forecasting.schemas import (
    IntentConfidence,
    IntentType,
    UserIntent,
)
from apps.api.main import app


def _intent(**overrides) -> UserIntent:
    base = dict(
        id=uuid4(),
        user_id=uuid4(),
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=80000.0,
        amount_delta=None,
        category_bucket="entertainment",
        start_date=date(2026, 5, 15),
        end_date=None,
        confidence=IntentConfidence.HIGH,
        is_recurring=False,
        rrule_freq=None,
        notes=None,
        is_active=True,
        created_at="2026-04-17T00:00:00+00:00",
        updated_at="2026-04-17T00:00:00+00:00",
    )
    base.update(overrides)
    return UserIntent(**base)


def _override_auth():
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-id", email=None)
    app.dependency_overrides[get_user_client] = lambda: MagicMock()


def _override_service(svc):
    app.dependency_overrides[_get_intents_service] = lambda: svc


@pytest.fixture(autouse=True)
def _disable_rate_limits():
    yield
    app.dependency_overrides.clear()


def test_create_intent_201():
    svc = MagicMock(spec=IntentsService)
    intent = _intent()
    svc.create.return_value = intent

    _override_auth()
    _override_service(svc)
    with TestClient(app) as tc:
        app.state.intent_crud_rate_limiter = None
        resp = tc.post(
            "/api/v1/forecast/intents",
            json={
                "intent_type": "planned_large_expense",
                "amount": 80000.0,
                "start_date": "2026-05-15",
                "confidence": "high",
                "category_bucket": "entertainment",
            },
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["intent_type"] == "planned_large_expense"
    assert body["amount"] == 80000.0


def test_list_intents_returns_array():
    svc = MagicMock(spec=IntentsService)
    svc.list.return_value = [_intent(), _intent(intent_type=IntentType.LIFE_EVENT, amount=None)]

    _override_auth()
    _override_service(svc)
    with TestClient(app) as tc:
        app.state.intent_crud_rate_limiter = None
        resp = tc.get("/api/v1/forecast/intents")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2


def test_get_intent_404_when_missing():
    svc = MagicMock(spec=IntentsService)
    svc.get.return_value = None

    _override_auth()
    _override_service(svc)
    with TestClient(app) as tc:
        app.state.intent_crud_rate_limiter = None
        resp = tc.get(f"/api/v1/forecast/intents/{uuid4()}")
    assert resp.status_code == 404


def test_patch_intent_returns_updated():
    svc = MagicMock(spec=IntentsService)
    intent = _intent(confidence=IntentConfidence.LOW)
    svc.update.return_value = intent

    _override_auth()
    _override_service(svc)
    with TestClient(app) as tc:
        app.state.intent_crud_rate_limiter = None
        resp = tc.patch(
            f"/api/v1/forecast/intents/{intent.id}",
            json={"confidence": "low"},
        )
    assert resp.status_code == 200
    assert resp.json()["confidence"] == "low"


def test_patch_intent_404_when_missing():
    svc = MagicMock(spec=IntentsService)
    svc.update.side_effect = LookupError("nope")

    _override_auth()
    _override_service(svc)
    with TestClient(app) as tc:
        app.state.intent_crud_rate_limiter = None
        resp = tc.patch(
            f"/api/v1/forecast/intents/{uuid4()}",
            json={"is_active": False},
        )
    assert resp.status_code == 404


def test_delete_intent_204():
    svc = MagicMock(spec=IntentsService)
    svc.delete.return_value = _intent(is_active=False)

    _override_auth()
    _override_service(svc)
    with TestClient(app) as tc:
        app.state.intent_crud_rate_limiter = None
        resp = tc.delete(f"/api/v1/forecast/intents/{uuid4()}")
    assert resp.status_code == 204


def test_intents_endpoints_require_authentication():
    """Without override, real auth dep should reject."""
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(_get_intents_service, None)
    with TestClient(app) as tc:
        app.state.intent_crud_rate_limiter = None
        resp = tc.get("/api/v1/forecast/intents")
    assert resp.status_code == 401
