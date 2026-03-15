# apps/api/domains/aggregator/tests/test_setu_provider.py
"""Tests for SetuProvider — uses injected mock HTTP client."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api.domains.aggregator.providers.setu import SetuProvider


def _mock_response(status_code: int, json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.fixture
def mock_http():
    return AsyncMock()


@pytest.fixture
def setu(mock_http):
    return SetuProvider(
        client_id="test-id",
        client_secret="test-secret",
        base_url="https://fiu-sandbox.setu.co",
        redirect_url="http://localhost:3000/dashboard/accounts/callback",
        http_client=mock_http,
    )


@pytest.mark.asyncio
async def test_initiate_consent(setu, mock_http):
    mock_http.post.return_value = _mock_response(
        201,
        {
            "id": "consent-123",
            "url": "https://anumati.setu.co/consent/123",
            "status": "PENDING",
        },
    )
    result = await setu.initiate_consent("user-1", ["DEPOSIT"])
    assert result["consent_id"] == "consent-123"
    assert "anumati.setu.co" in result["redirect_url"]


@pytest.mark.asyncio
async def test_check_consent_status(setu, mock_http):
    mock_http.get.return_value = _mock_response(
        200,
        {
            "id": "consent-123",
            "status": "ACTIVE",
            "detail": {"fiTypes": ["DEPOSIT"], "consentExpiry": "2027-03-15T00:00:00Z"},
        },
    )
    result = await setu.check_consent_status("consent-123")
    assert result["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_fetch_transactions_normalizes(setu, mock_http):
    mock_http.post.return_value = _mock_response(
        200,
        {
            "fi": [
                {
                    "data": {
                        "account": {"maskedAccNumber": "XXXX1234", "type": "SAVINGS"},
                        "transactions": [
                            {
                                "txnId": "txn-1",
                                "type": "DEBIT",
                                "amount": "1500.00",
                                "narration": "AMAZON PURCHASE",
                                "transactionTimestamp": "2026-03-10T14:30:00Z",
                                "reference": "REF123",
                                "mode": "UPI",
                            }
                        ],
                    }
                }
            ],
        },
    )
    txns = await setu.fetch_transactions(
        "c-1", datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 3, 15, tzinfo=timezone.utc)
    )
    assert len(txns) == 1
    assert txns[0]["amount"] == -1500.00
    assert txns[0]["payment_method"] == "UPI"


@pytest.mark.asyncio
async def test_revoke_consent(setu, mock_http):
    mock_http.post.return_value = _mock_response(200, {})
    await setu.revoke_consent("consent-123")
    assert "consent-123/revoke" in mock_http.post.call_args[0][0]


@pytest.mark.asyncio
async def test_raises_on_error(setu, mock_http):
    error_resp = _mock_response(500, {"error": "internal"})
    error_resp.raise_for_status.side_effect = Exception("500 Server Error")
    mock_http.post.return_value = error_resp
    with pytest.raises(Exception, match="500"):
        await setu.initiate_consent("user-1", ["DEPOSIT"])
