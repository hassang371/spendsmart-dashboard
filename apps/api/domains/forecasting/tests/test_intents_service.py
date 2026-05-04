"""IntentsService CRUD + bridge orchestration tests.

Mock the user-scoped supabase client; assert the service calls the
``upsert_intent_with_bridge`` RPC with the correct payload, lists by
filter, fetches by id, and soft-deletes via PATCH-style update.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md §Component Architecture
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from apps.api.domains.forecasting.intents_service import IntentsService
from apps.api.domains.forecasting.schemas import (
    IntentConfidence,
    IntentCreateRequest,
    IntentType,
    IntentUpdateRequest,
)


def _intent_row(**overrides):
    base = {
        "id": str(uuid4()),
        "user_id": str(uuid4()),
        "intent_type": "planned_large_expense",
        "amount": 80000.0,
        "amount_delta": None,
        "category_bucket": "entertainment",
        "start_date": "2026-05-15",
        "end_date": None,
        "confidence": "high",
        "is_recurring": False,
        "rrule_freq": None,
        "notes": None,
        "is_active": True,
        "created_at": "2026-04-17T00:00:00+00:00",
        "updated_at": "2026-04-17T00:00:00+00:00",
    }
    base.update(overrides)
    return base


def _make_client_with_rpc(return_data):
    """Build a supabase client mock whose .rpc().execute().data returns ``return_data``."""
    client = MagicMock()
    rpc_resp = MagicMock()
    rpc_resp.execute.return_value = MagicMock(data=return_data)
    client.rpc.return_value = rpc_resp
    return client


def _make_client_with_table(rows):
    client = MagicMock()
    tbl = MagicMock()
    select = MagicMock()
    select.execute.return_value = MagicMock(data=rows)
    chain = MagicMock()
    chain.eq.return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    select.eq.return_value = chain
    tbl.select.return_value = select
    client.table.return_value = tbl
    return client, tbl, select, chain


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_dated_intent_calls_rpc_with_bridge_payload():
    user_id = str(uuid4())
    intent_id = str(uuid4())
    row = _intent_row(id=intent_id, user_id=user_id)
    client = _make_client_with_rpc(return_data=row)

    svc = IntentsService(client)
    req = IntentCreateRequest(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=80000.0,
        start_date=date(2026, 5, 15),
        confidence=IntentConfidence.HIGH,
        category_bucket="entertainment",
    )
    result = svc.create(req, user_id=user_id)

    # Result is a UserIntent built from the RPC response row.
    assert str(result.id) == intent_id
    assert result.intent_type is IntentType.PLANNED_LARGE_EXPENSE

    # The RPC was called with the right name + a payload that requests
    # the bridge.
    name, kwargs = client.rpc.call_args[0]
    assert name == "upsert_intent_with_bridge"
    payload = kwargs["payload"]
    assert payload["user_id"] == user_id
    assert payload["intent_type"] == "planned_large_expense"
    assert payload["should_bridge"] is True
    bridge = payload["bridge_row"]
    assert bridge["amount"] == -80000.0
    assert bridge["source"] == "intent"


def test_create_life_event_does_not_request_bridge():
    user_id = str(uuid4())
    row = _intent_row(intent_type="life_event", user_id=user_id, amount=None)
    client = _make_client_with_rpc(return_data=row)

    svc = IntentsService(client)
    req = IntentCreateRequest(
        intent_type=IntentType.LIFE_EVENT,
        start_date=date(2026, 8, 1),
    )
    svc.create(req, user_id=user_id)

    payload = client.rpc.call_args[0][1]["payload"]
    assert payload["should_bridge"] is False
    assert payload.get("bridge_row") is None


def test_create_savings_goal_does_not_request_bridge():
    user_id = str(uuid4())
    row = _intent_row(
        intent_type="savings_goal",
        user_id=user_id,
        amount=200000.0,
        end_date="2026-12-31",
    )
    client = _make_client_with_rpc(return_data=row)
    svc = IntentsService(client)
    req = IntentCreateRequest(
        intent_type=IntentType.SAVINGS_GOAL,
        amount=200000.0,
        start_date=date(2026, 5, 1),
        end_date=date(2026, 12, 31),
    )
    svc.create(req, user_id=user_id)
    payload = client.rpc.call_args[0][1]["payload"]
    assert payload["should_bridge"] is False


def test_create_low_confidence_dated_writes_zero_amount_bridge_row():
    user_id = str(uuid4())
    row = _intent_row(user_id=user_id, confidence="low", amount=10000.0)
    client = _make_client_with_rpc(return_data=row)
    svc = IntentsService(client)
    req = IntentCreateRequest(
        intent_type=IntentType.PLANNED_LARGE_EXPENSE,
        amount=10000.0,
        start_date=date(2026, 5, 1),
        confidence=IntentConfidence.LOW,
    )
    svc.create(req, user_id=user_id)
    payload = client.rpc.call_args[0][1]["payload"]
    assert payload["bridge_row"]["amount"] == 0.0


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------


def test_update_calls_rpc_with_intent_id_and_bridge_for_dated():
    user_id = str(uuid4())
    intent_id = str(uuid4())

    # First the service fetches the existing intent to know the type:
    existing = _intent_row(id=intent_id, user_id=user_id)
    after = _intent_row(id=intent_id, user_id=user_id, confidence="medium", amount=50000.0)

    client = MagicMock()
    # .table(...).select().eq().eq().execute().data -> [existing]
    select_resp = MagicMock()
    eq2 = MagicMock()
    eq2.execute.return_value = MagicMock(data=[existing])
    eq1 = MagicMock()
    eq1.eq.return_value = eq2
    select_resp.eq.return_value = eq1
    select_chain = MagicMock()
    select_chain.select.return_value = select_resp
    client.table.return_value = select_chain

    rpc_resp = MagicMock()
    rpc_resp.execute.return_value = MagicMock(data=after)
    client.rpc.return_value = rpc_resp

    svc = IntentsService(client)
    req = IntentUpdateRequest(amount=50000.0, confidence=IntentConfidence.MEDIUM)
    result = svc.update(intent_id, req, user_id=user_id)
    assert result.confidence is IntentConfidence.MEDIUM

    payload = client.rpc.call_args[0][1]["payload"]
    assert payload["id"] == intent_id
    assert payload["should_bridge"] is True
    # 70% × 50000 = 35000, negative for PLANNED_LARGE_EXPENSE
    assert payload["bridge_row"]["amount"] == pytest.approx(-35000.0)


# ---------------------------------------------------------------------------
# delete (soft)
# ---------------------------------------------------------------------------


def test_delete_soft_deletes_via_is_active_false():
    user_id = str(uuid4())
    intent_id = str(uuid4())
    existing = _intent_row(id=intent_id, user_id=user_id)
    after = _intent_row(id=intent_id, user_id=user_id, is_active=False)

    client = MagicMock()
    select_resp = MagicMock()
    eq2 = MagicMock()
    eq2.execute.return_value = MagicMock(data=[existing])
    eq1 = MagicMock()
    eq1.eq.return_value = eq2
    select_resp.eq.return_value = eq1
    select_chain = MagicMock()
    select_chain.select.return_value = select_resp
    client.table.return_value = select_chain

    rpc_resp = MagicMock()
    rpc_resp.execute.return_value = MagicMock(data=after)
    client.rpc.return_value = rpc_resp

    svc = IntentsService(client)
    svc.delete(intent_id, user_id=user_id)
    payload = client.rpc.call_args[0][1]["payload"]
    assert payload["id"] == intent_id
    assert payload["is_active"] is False


# ---------------------------------------------------------------------------
# get / list
# ---------------------------------------------------------------------------


def test_get_returns_user_intent():
    user_id = str(uuid4())
    intent_id = str(uuid4())
    row = _intent_row(id=intent_id, user_id=user_id)
    client = MagicMock()
    select_resp = MagicMock()
    eq2 = MagicMock()
    eq2.execute.return_value = MagicMock(data=[row])
    eq1 = MagicMock()
    eq1.eq.return_value = eq2
    select_resp.eq.return_value = eq1
    select_chain = MagicMock()
    select_chain.select.return_value = select_resp
    client.table.return_value = select_chain

    svc = IntentsService(client)
    result = svc.get(intent_id, user_id=user_id)
    assert str(result.id) == intent_id


def test_get_missing_returns_none():
    user_id = str(uuid4())
    intent_id = str(uuid4())
    client = MagicMock()
    select_resp = MagicMock()
    eq2 = MagicMock()
    eq2.execute.return_value = MagicMock(data=[])
    eq1 = MagicMock()
    eq1.eq.return_value = eq2
    select_resp.eq.return_value = eq1
    select_chain = MagicMock()
    select_chain.select.return_value = select_resp
    client.table.return_value = select_chain

    svc = IntentsService(client)
    assert svc.get(intent_id, user_id=user_id) is None


def test_list_filters_by_user_id_and_active_default():
    user_id = str(uuid4())
    rows = [_intent_row(user_id=user_id) for _ in range(3)]
    client = MagicMock()
    select_resp = MagicMock()
    eq_chain = MagicMock()
    eq_chain.eq.return_value = eq_chain
    eq_chain.execute.return_value = MagicMock(data=rows)
    select_resp.eq.return_value = eq_chain
    select_chain = MagicMock()
    select_chain.select.return_value = select_resp
    client.table.return_value = select_chain

    svc = IntentsService(client)
    result = svc.list(user_id=user_id, include_inactive=False)
    assert len(result) == 3
    # The first .eq filters user_id; the chained .eq should filter is_active=True.
    eq_chain.eq.assert_any_call("is_active", True)
