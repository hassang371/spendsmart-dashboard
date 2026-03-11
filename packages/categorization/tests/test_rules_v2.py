"""Tests for the v2 keyword rules engine and category constants."""

import pytest

from packages.categorization.constants import (
    DEFAULT_CATEGORY_KEYWORDS,
    LEGACY_CATEGORY_MAP,
    Category,
)
from packages.categorization.rules import KeywordMatcher


@pytest.fixture
def matcher():
    return KeywordMatcher()


# ── Category Constants Tests ────────────────────────────────────────────


class TestCategoryConstants:
    """Test expanded category taxonomy."""

    def test_category_count_is_at_least_25(self):
        assert len(Category) >= 25

    def test_all_categories_have_seed_phrases(self):
        for cat in Category:
            assert cat.value in DEFAULT_CATEGORY_KEYWORDS, f"Missing seeds for {cat.value}"

    def test_legacy_map_covers_old_categories(self):
        old_cats = [
            "Food",
            "Transport",
            "Utilities",
            "Salary",
            "Shopping",
            "Entertainment",
            "Health",
            "Education",
            "Finance",
            "People",
            "Misc",
            "Uncategorized",
        ]
        for old in old_cats:
            assert old in LEGACY_CATEGORY_MAP, f"Missing legacy mapping for {old}"
            assert LEGACY_CATEGORY_MAP[old] in [c.value for c in Category]


# ── Keyword Matcher Tests ───────────────────────────────────────────────


class TestKeywordMatcherDining:
    def test_swiggy_matches_dining(self, matcher):
        result = matcher.predict("Swiggy food delivery")
        assert result is not None
        assert result["category"] == Category.FOOD.value
        assert result["confidence"] == 1.0

    def test_zomato_matches_dining(self, matcher):
        result = matcher.predict("Zomato order payment")
        assert result is not None
        assert result["category"] == Category.FOOD.value

    def test_dominos_matches_dining(self, matcher):
        result = matcher.predict("Dominos pizza order")
        assert result is not None
        assert result["category"] == Category.FOOD.value


class TestKeywordMatcherGroceries:
    def test_blinkit_matches_groceries(self, matcher):
        result = matcher.predict("Blinkit delivery")
        assert result is not None
        assert result["category"] == Category.GROCERIES.value

    def test_zepto_matches_groceries(self, matcher):
        result = matcher.predict("Zepto quick delivery")
        assert result is not None
        assert result["category"] == Category.GROCERIES.value

    def test_bigbasket_matches_groceries(self, matcher):
        result = matcher.predict("Bigbasket grocery order")
        assert result is not None
        assert result["category"] == Category.GROCERIES.value


class TestKeywordMatcherTransport:
    def test_uber_matches_taxi(self, matcher):
        result = matcher.predict("Uber ride payment")
        assert result is not None
        assert result["category"] == Category.TAXI_RIDESHARE.value

    def test_ola_matches_taxi(self, matcher):
        result = matcher.predict("Ola cab trip")
        assert result is not None
        assert result["category"] == Category.TAXI_RIDESHARE.value


class TestKeywordMatcherHotels:
    def test_airbnb_matches_hotels(self, matcher):
        result = matcher.predict("Airbnb accommodation booking")
        assert result is not None
        assert result["category"] == Category.HOTELS_STAYS.value

    def test_oyo_matches_hotels(self, matcher):
        result = matcher.predict("OYO hotel room stay")
        assert result is not None
        assert result["category"] == Category.HOTELS_STAYS.value


class TestKeywordMatcherFinance:
    def test_zerodha_matches_investments(self, matcher):
        result = matcher.predict("Zerodha brokerage")
        assert result is not None
        assert result["category"] == Category.INVESTMENTS.value


class TestKeywordMatcherPeople:
    def test_upi_transfer_to_person(self, matcher):
        result = matcher.predict("UPI Transfer to Allan G via YESB")
        assert result is not None
        assert result["category"] == Category.TRANSFERS_TO_PEOPLE.value

    def test_received_from_person(self, matcher):
        result = matcher.predict("UPI Received from Lakshmi via KKBK")
        assert result is not None
        assert result["category"] == Category.RECEIVED_FROM_PEOPLE.value

    def test_transfer_to_swiggy_stays_dining(self, matcher):
        """If we transfer to Swiggy via UPI, it should match Dining, not People."""
        result = matcher.predict("UPI Transfer to Swiggy via HDFC")
        assert result is not None
        assert result["category"] == Category.FOOD.value

    def test_sent_to_person(self, matcher):
        result = matcher.predict("Sent to Hassan via UPI")
        assert result is not None
        assert result["category"] == Category.TRANSFERS_TO_PEOPLE.value


class TestKeywordMatcherEdgeCases:
    def test_empty_string_returns_none(self, matcher):
        assert matcher.predict("") is None

    def test_none_returns_none(self, matcher):
        assert matcher.predict(None) is None

    def test_unknown_text_returns_none(self, matcher):
        assert matcher.predict("random gibberish xyz abc") is None

    def test_case_insensitive(self, matcher):
        result = matcher.predict("NETFLIX subscription")
        assert result is not None
        assert result["category"] == Category.SUBSCRIPTIONS.value
