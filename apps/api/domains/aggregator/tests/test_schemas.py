# apps/api/domains/aggregator/tests/test_schemas.py
"""Tests for aggregator Pydantic schemas."""

from datetime import datetime, timezone

from apps.api.domains.aggregator.schemas import (
    BankAccountOut,
    LinkAccountRequest,
    LinkAccountResponse,
    SyncResponse,
    WebhookEvent,
)


def test_bank_account_out_from_db_row():
    row = {
        "id": "abc-123",
        "user_id": "user-1",
        "account_name": "HDFC ****1234",
        "account_type": "savings",
        "institution": "HDFC Bank",
        "provider": "setu",
        "consent_status": "active",
        "last_synced_at": "2026-03-15T10:00:00Z",
        "sync_status": "idle",
        "is_primary": False,
        "is_manual": False,
        "masked_number": "****1234",
        "currency": "INR",
        "created_at": "2026-03-15T09:00:00Z",
        "updated_at": "2026-03-15T10:00:00Z",
    }
    account = BankAccountOut(**row)
    assert account.account_name == "HDFC ****1234"


def test_link_account_request_defaults():
    assert LinkAccountRequest().fi_types == ["DEPOSIT"]


def test_link_account_response():
    resp = LinkAccountResponse(redirect_url="https://setu.co/consent", consent_id="c1")
    assert resp.redirect_url == "https://setu.co/consent"


def test_sync_response():
    assert SyncResponse(inserted=47, skipped_duplicates=3, account_id="abc").inserted == 47


def test_webhook_event():
    event = WebhookEvent(consent_id="c1", status="ACTIVE", timestamp=datetime(2026, 3, 15, tzinfo=timezone.utc))
    assert event.status == "ACTIVE"


def test_webhook_event_optional_timestamp():
    assert WebhookEvent(consent_id="c1", status="ACTIVE").timestamp is None
