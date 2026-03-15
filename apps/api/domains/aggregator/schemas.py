# apps/api/domains/aggregator/schemas.py
"""Pydantic models for the aggregator domain."""

from datetime import datetime

from pydantic import BaseModel, Field


class BankAccountOut(BaseModel):
    id: str
    user_id: str
    account_name: str
    account_type: str
    institution: str | None = None
    provider: str | None = None
    consent_status: str
    last_synced_at: datetime | None = None
    sync_status: str
    is_primary: bool
    is_manual: bool
    masked_number: str | None = None
    currency: str
    created_at: datetime
    updated_at: datetime


class LinkAccountRequest(BaseModel):
    fi_types: list[str] = Field(default_factory=lambda: ["DEPOSIT"])


class LinkAccountResponse(BaseModel):
    redirect_url: str
    consent_id: str


class SyncResponse(BaseModel):
    inserted: int
    skipped_duplicates: int
    account_id: str


class WebhookEvent(BaseModel):
    consent_id: str
    status: str
    timestamp: datetime | None = None
