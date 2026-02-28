"""Pydantic schemas for the ingestion domain."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TransactionOut(BaseModel):
    """A parsed, fingerprinted transaction ready for display or insert."""

    date: str
    amount: float
    merchant: str = ""
    description: str = ""
    category: str = "Uncategorized"
    confidence: float = 0.0
    fingerprint: str
    payment_method: str = ""
    currency: str = "USD"
    type: str = ""  # "credit" or "debit"
    raw_data: dict = Field(default_factory=dict)


class IngestResponse(BaseModel):
    """Response from CSV ingestion."""

    transactions: list[TransactionOut]
    count: int
    duplicates_skipped: int = 0
