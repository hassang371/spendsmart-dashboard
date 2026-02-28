"""Accounts domain schemas — response models for transactions and profiles.

These models provide rich OpenAPI documentation with field descriptions
and examples for auto-generated API docs.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TransactionOut(BaseModel):
    """A single user transaction as returned by the API."""

    id: str = Field(description="Unique transaction UUID", examples=["a1b2c3d4-e5f6-7890-abcd-ef1234567890"])
    user_id: str = Field(description="Owner user UUID", examples=["u1234-5678-abcd"])
    transaction_date: Optional[str] = Field(default=None, description="ISO 8601 timestamp", examples=["2026-01-15T10:30:00+05:30"])
    amount: float = Field(description="Transaction amount (positive=credit, negative=debit)", examples=[-50.0])
    currency: Optional[str] = Field(default="INR", description="ISO 4217 currency code", examples=["INR"])
    description: Optional[str] = Field(default=None, description="Transaction description", examples=["Coffee at Starbucks"])
    merchant_name: Optional[str] = Field(default=None, description="Merchant name", examples=["Starbucks"])
    category: Optional[str] = Field(default="Uncategorized", description="Transaction category", examples=["Food & Dining"])
    payment_method: Optional[str] = Field(default=None, description="Payment method", examples=["card"])
    status: Optional[str] = Field(default="completed", description="Transaction status", examples=["completed"])
    type: Optional[str] = Field(default=None, description="Transaction type: credit or debit", examples=["debit"])
    fingerprint: Optional[str] = Field(default=None, description="SHA256 dedup fingerprint")
    is_manual: Optional[bool] = Field(default=False, description="Whether manually entered")
    created_at: Optional[str] = Field(default=None, description="Record creation timestamp")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "user_id": "u1234-5678-abcd",
                    "transaction_date": "2026-01-15T10:30:00+05:30",
                    "amount": -50.0,
                    "currency": "INR",
                    "description": "Coffee at Starbucks",
                    "merchant_name": "Starbucks",
                    "category": "Food & Dining",
                    "payment_method": "card",
                    "status": "completed",
                    "type": "debit",
                    "is_manual": False,
                }
            ]
        }
    }


class ProfileOut(BaseModel):
    """User profile response."""

    id: str = Field(description="User UUID")
    email: Optional[str] = Field(default=None, description="User email address")
