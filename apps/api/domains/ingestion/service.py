"""Ingestion service — business logic for parsing, fingerprinting, dedup.

Fixes BUG-02: Unifies fingerprinting into a single 6-field SHA256 algorithm
that matches the Next.js buildFingerprint implementation. Both Python and JS
paths now produce identical fingerprints for the same transaction.
"""

import hashlib
from typing import Optional


def generate_fingerprint(
    date: str,
    amount: float,
    merchant: str,
    description: str = "",
    payment_method: str = "",
    reference: str = "",
) -> str:
    """Generate a deterministic SHA256 fingerprint for a transaction.

    Uses the same 6-field algorithm as the Next.js buildFingerprint:
        SHA256(date[:19]|amount.toFixed(2)|MERCHANT|DESCRIPTION|PAYMENT_METHOD|REFERENCE)

    All string fields are trimmed and uppercased for case-insensitive matching.
    The amount is normalized to 2 decimal places (matching JS `toFixed(2)`).
    The date is truncated to 19 characters to strip timezone suffixes.

    Args:
        date: ISO 8601 date string.
        amount: Transaction amount (positive=credit, negative=debit).
        merchant: Merchant name.
        description: Transaction description.
        payment_method: Payment method (e.g., "card", "cash").
        reference: External reference/ID.

    Returns:
        64-character lowercase hex SHA256 hash.
    """
    normalized_date = date[:19]
    normalized_amount = f"{amount:.2f}"
    normalized_merchant = merchant.strip().upper()
    normalized_description = description.strip().upper()
    normalized_payment = payment_method.strip().upper()
    normalized_reference = reference.strip().upper()

    raw = (
        f"{normalized_date}|{normalized_amount}|{normalized_merchant}"
        f"|{normalized_description}|{normalized_payment}|{normalized_reference}"
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
