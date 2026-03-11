"""Pydantic schemas for the ingestion domain.

Provides rich OpenAPI documentation for transaction import flow.
"""

from pydantic import BaseModel, Field


class TransactionOut(BaseModel):
    """A parsed, fingerprinted transaction ready for display or insert."""

    date: str = Field(description="Transaction date (ISO 8601)", examples=["2026-01-15"])
    amount: float = Field(description="Transaction amount", examples=[-50.0])
    merchant: str = Field(default="", description="Merchant name", examples=["Starbucks"])
    description: str = Field(default="", description="Transaction description", examples=["Coffee purchase"])
    category: str = Field(
        default="Uncategorized",
        description="Predicted category",
        examples=["Food & Dining"],
    )
    confidence: float = Field(default=0.0, description="Classification confidence 0-1", examples=[0.92])
    fingerprint: str = Field(description="SHA256 dedup fingerprint (64-char hex)")
    payment_method: str = Field(default="", description="Payment method", examples=["card"])
    currency: str = Field(default="USD", description="ISO 4217 currency code", examples=["INR"])
    type: str = Field(default="", description="Transaction type: credit or debit", examples=["debit"])
    raw_data: dict = Field(default_factory=dict, description="Original parsed row data")


class IngestResponse(BaseModel):
    """Response from CSV/Excel ingestion endpoint."""

    transactions: list[TransactionOut] = Field(description="Parsed and fingerprinted transactions")
    count: int = Field(description="Number of transactions parsed", examples=[42])
    duplicates_skipped: int = Field(default=0, description="Duplicates skipped via fingerprint", examples=[3])
