# apps/api/domains/aggregator/tests/test_service.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.domains.aggregator import service


def _mock_supabase(query_data=None):
    client = MagicMock()
    result = MagicMock()
    result.data = query_data or []
    chain = MagicMock()
    chain.execute.return_value = result
    for m in ("eq", "neq", "order", "select", "insert", "update", "delete", "limit"):
        getattr(chain, m).return_value = chain
    client.table.return_value = chain
    rpc_result = MagicMock()
    rpc_result.data = [{"inserted_count": 5, "skipped_count": 0}]
    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = rpc_result
    client.rpc.return_value = rpc_chain
    return client


@pytest.mark.asyncio
async def test_list_accounts():
    accounts = [{"id": "acc-1"}]
    result = await service.list_accounts(_mock_supabase(accounts), "user-1")
    assert result == accounts


@pytest.mark.asyncio
async def test_get_or_create_manual_returns_existing():
    existing = [{"id": "acc-m", "is_manual": True}]
    result = await service.get_or_create_manual_account(_mock_supabase(existing), "user-1")
    assert result["id"] == "acc-m"


@pytest.mark.asyncio
async def test_get_or_create_manual_creates_new():
    client = _mock_supabase([])
    new = {"id": "acc-new", "is_manual": True}
    client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[new])
    result = await service.get_or_create_manual_account(client, "user-1")
    assert result["id"] == "acc-new"


@pytest.mark.asyncio
async def test_link_account():
    provider = AsyncMock()
    provider.initiate_consent.return_value = {"consent_id": "c-1", "redirect_url": "https://setu.co/c-1"}
    result = await service.link_account(_mock_supabase([]), "user-1", provider, ["DEPOSIT"])
    assert result["consent_id"] == "c-1"
    provider.initiate_consent.assert_called_once()


@pytest.mark.asyncio
async def test_handle_callback_active():
    account = {"id": "acc-1", "user_id": "user-1"}
    provider = AsyncMock()
    provider.check_consent_status.return_value = {"status": "ACTIVE", "detail": {"consentExpiry": "2027-03-15"}}
    result = await service.handle_callback(_mock_supabase([account]), "c-1", provider)
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_handle_callback_rejected():
    account = {"id": "acc-1", "user_id": "user-1"}
    provider = AsyncMock()
    provider.check_consent_status.return_value = {"status": "REJECTED"}
    result = await service.handle_callback(_mock_supabase([account]), "c-1", provider)
    assert result["status"] == "rejected"


@pytest.mark.asyncio
async def test_sync_account():
    account = {"id": "acc-1", "user_id": "user-1", "consent_id": "c-1", "last_synced_at": None}
    provider = AsyncMock()
    provider.fetch_transactions.return_value = [
        {
            "transaction_date": "2026-03-10T14:30:00",
            "amount": -1500.00,
            "description": "AMAZON",
            "merchant_name": "",
            "payment_method": "UPI",
            "reference": "REF1",
        }
    ]
    result = await service.sync_account(_mock_supabase([account]), "acc-1", provider)
    assert "inserted" in result


@pytest.mark.asyncio
async def test_unlink_manual_raises():
    manual = {"id": "acc-m", "is_manual": True, "consent_id": None, "consent_status": "none"}
    with pytest.raises(ValueError, match="Cannot unlink"):
        await service.unlink_account(_mock_supabase([manual]), "acc-m", AsyncMock())


@pytest.mark.asyncio
async def test_unlink_revokes_consent():
    account = {"id": "acc-1", "is_manual": False, "consent_id": "c-1", "consent_status": "active"}
    provider = AsyncMock()
    await service.unlink_account(_mock_supabase([account]), "acc-1", provider)
    provider.revoke_consent.assert_called_once_with("c-1")
