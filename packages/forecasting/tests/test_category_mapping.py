"""Tests for RFC-005 §1 H1 — classifier label → bucket mapping."""

from __future__ import annotations

from packages.categorization.constants import Category
from packages.forecasting.buckets import CATEGORY_BUCKETS
from packages.forecasting.category_mapping import (
    CLASSIFIER_LABEL_TO_BUCKET,
    map_classifier_label_to_bucket,
)


def test_every_classifier_label_maps():
    """100% coverage: every Category enum value has a bucket entry."""
    missing: list[str] = []
    for cat in Category:
        if cat.value not in CLASSIFIER_LABEL_TO_BUCKET:
            missing.append(cat.value)
    assert not missing, f"Missing bucket mapping for: {missing}"


def test_every_mapped_value_is_in_bucket_taxonomy():
    """The mapping cannot route to a bucket name outside the 12-bucket
    taxonomy."""
    for label, bucket in CLASSIFIER_LABEL_TO_BUCKET.items():
        assert bucket in CATEGORY_BUCKETS, f"Label {label!r} maps to unknown bucket {bucket!r}"


def test_rfc005_h1_routings():
    """Insurance / Taxes / Bank Fees / Home Maintenance route to 'other'."""
    assert map_classifier_label_to_bucket(Category.INSURANCE.value) == "other"
    assert map_classifier_label_to_bucket(Category.TAXES.value) == "other"
    assert map_classifier_label_to_bucket(Category.BANK_FEES.value) == "other"
    assert map_classifier_label_to_bucket(Category.HOME_MAINTENANCE.value) == "other"


def test_unknown_label_falls_back_to_other():
    assert map_classifier_label_to_bucket("not-a-category") == "other"


def test_none_and_empty_fall_back_to_other():
    assert map_classifier_label_to_bucket(None) == "other"
    assert map_classifier_label_to_bucket("") == "other"
    assert map_classifier_label_to_bucket("   ") == "other"


def test_lookup_is_case_insensitive():
    assert map_classifier_label_to_bucket("salary") == "salary"
    assert map_classifier_label_to_bucket("SALARY") == "salary"
    assert map_classifier_label_to_bucket("  Salary  ") == "salary"


def test_canonical_routings_match_rfc():
    """Spot-check some canonical mappings from RFC-005 §1."""
    assert map_classifier_label_to_bucket(Category.SALARY.value) == "salary"
    assert map_classifier_label_to_bucket(Category.RENT_MORTGAGE.value) == "rent"
    assert map_classifier_label_to_bucket(Category.GROCERIES.value) == "groceries"
    assert map_classifier_label_to_bucket(Category.SUBSCRIPTIONS.value) == "entertainment"
    assert map_classifier_label_to_bucket(Category.LOAN_EMI.value) == "emi_loan"
    assert map_classifier_label_to_bucket(Category.INVESTMENTS.value) == "investment"
    assert map_classifier_label_to_bucket(Category.TRANSFERS_TO_PEOPLE.value) == "transfer"
