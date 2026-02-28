"""Tests for ingestion domain — fingerprinting, service, router."""

import pytest

from apps.api.domains.ingestion.service import generate_fingerprint


class TestFingerprint:
    """BUG-02 fix: Unified 6-field fingerprint must be deterministic and
    match the Next.js buildFingerprint algorithm."""

    def test_same_input_same_fingerprint(self):
        """Identical inputs must always produce the same SHA256."""
        fp1 = generate_fingerprint(
            date="2026-01-15",
            amount=50.00,
            merchant="Starbucks",
            description="Coffee",
            payment_method="card",
            reference="",
        )
        fp2 = generate_fingerprint(
            date="2026-01-15",
            amount=50.00,
            merchant="Starbucks",
            description="Coffee",
            payment_method="card",
            reference="",
        )
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA256 hex

    def test_case_insensitive(self):
        """Merchant, description, etc. should be uppercased before hashing."""
        fp_lower = generate_fingerprint(
            date="2026-01-15",
            amount=50.00,
            merchant="starbucks",
            description="coffee",
            payment_method="Card",
            reference="",
        )
        fp_upper = generate_fingerprint(
            date="2026-01-15",
            amount=50.00,
            merchant="STARBUCKS",
            description="COFFEE",
            payment_method="CARD",
            reference="",
        )
        assert fp_lower == fp_upper

    def test_amount_normalized_to_two_decimals(self):
        """50 and 50.00 should produce same fingerprint (matches JS toFixed(2))."""
        fp_int = generate_fingerprint(
            date="2026-01-15",
            amount=50,
            merchant="Starbucks",
            description="Coffee",
            payment_method="card",
            reference="",
        )
        fp_float = generate_fingerprint(
            date="2026-01-15",
            amount=50.00,
            merchant="Starbucks",
            description="Coffee",
            payment_method="card",
            reference="",
        )
        assert fp_int == fp_float

    def test_different_description_different_fingerprint(self):
        """Different descriptions should produce different fingerprints."""
        fp1 = generate_fingerprint(
            date="2026-01-15",
            amount=50.00,
            merchant="Starbucks",
            description="Coffee",
            payment_method="card",
            reference="",
        )
        fp2 = generate_fingerprint(
            date="2026-01-15",
            amount=50.00,
            merchant="Starbucks",
            description="Latte",
            payment_method="card",
            reference="",
        )
        assert fp1 != fp2

    def test_date_truncated_to_19_chars(self):
        """ISO date with timezone suffix should be truncated to first 19 chars."""
        fp_full = generate_fingerprint(
            date="2026-01-15T10:30:00",
            amount=50.00,
            merchant="Starbucks",
            description="Coffee",
            payment_method="card",
            reference="",
        )
        fp_tz = generate_fingerprint(
            date="2026-01-15T10:30:00+05:30",
            amount=50.00,
            merchant="Starbucks",
            description="Coffee",
            payment_method="card",
            reference="",
        )
        assert fp_full == fp_tz
