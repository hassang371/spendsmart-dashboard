"""Tests for query filtering module.

TDD: These tests define the expected behavior of core/filtering.py
before it exists. Tests use a mock Supabase query builder to verify
that filters chain the correct Supabase client calls.
"""

from unittest.mock import MagicMock

from apps.api.core.filtering import TransactionFilter, apply_filters


class TestTransactionFilter:
    """Tests for the TransactionFilter dataclass."""

    def test_all_defaults_none(self):
        """An empty filter has all None fields."""
        f = TransactionFilter()
        assert f.date_from is None
        assert f.date_to is None
        assert f.amount_min is None
        assert f.amount_max is None
        assert f.category is None
        assert f.merchant is None
        assert f.type is None

    def test_partial_filter(self):
        """Filters can be partially set."""
        f = TransactionFilter(category="Food", amount_min=10.0)
        assert f.category == "Food"
        assert f.amount_min == 10.0
        assert f.date_from is None


class TestApplyFilters:
    """Tests for the apply_filters function.

    Uses a mock Supabase query builder to verify that the correct
    chained method calls are made based on the filter values.
    """

    def _make_mock_query(self):
        """Create a mock Supabase query builder that returns itself on chaining."""
        query = MagicMock()
        query.gte.return_value = query
        query.lte.return_value = query
        query.eq.return_value = query
        query.ilike.return_value = query
        return query

    def test_no_filters_no_calls(self):
        """Empty filter should not add any WHERE clauses."""
        query = self._make_mock_query()
        result = apply_filters(query, TransactionFilter())
        # No filter methods should have been called
        query.gte.assert_not_called()
        query.lte.assert_not_called()
        query.eq.assert_not_called()
        query.ilike.assert_not_called()
        assert result is query

    def test_date_from_filter(self):
        """date_from adds a gte on transaction_date."""
        query = self._make_mock_query()
        f = TransactionFilter(date_from="2026-01-01")
        apply_filters(query, f)
        query.gte.assert_called_once_with("transaction_date", "2026-01-01")

    def test_date_to_filter(self):
        """date_to adds a lte on transaction_date."""
        query = self._make_mock_query()
        f = TransactionFilter(date_to="2026-12-31")
        apply_filters(query, f)
        query.lte.assert_called_once_with("transaction_date", "2026-12-31")

    def test_amount_min_filter(self):
        """amount_min adds a gte on amount."""
        query = self._make_mock_query()
        f = TransactionFilter(amount_min=10.0)
        apply_filters(query, f)
        query.gte.assert_called_once_with("amount", 10.0)

    def test_amount_max_filter(self):
        """amount_max adds a lte on amount."""
        query = self._make_mock_query()
        f = TransactionFilter(amount_max=500.0)
        apply_filters(query, f)
        query.lte.assert_called_once_with("amount", 500.0)

    def test_category_filter(self):
        """category adds an eq on category."""
        query = self._make_mock_query()
        f = TransactionFilter(category="Food")
        apply_filters(query, f)
        query.eq.assert_called_once_with("category", "Food")

    def test_merchant_filter(self):
        """merchant adds an ilike (case-insensitive search) on merchant_name."""
        query = self._make_mock_query()
        f = TransactionFilter(merchant="Starbucks")
        apply_filters(query, f)
        query.ilike.assert_called_once_with("merchant_name", "%Starbucks%")

    def test_type_filter(self):
        """type adds an eq on type."""
        query = self._make_mock_query()
        f = TransactionFilter(type="debit")
        apply_filters(query, f)
        query.eq.assert_called_once_with("type", "debit")

    def test_combined_filters(self):
        """Multiple filters are AND'd together via chaining."""
        query = self._make_mock_query()
        f = TransactionFilter(
            date_from="2026-01-01",
            date_to="2026-06-30",
            category="Food",
            amount_min=5.0,
        )
        result = apply_filters(query, f)
        # All relevant methods should be called
        query.gte.assert_any_call("transaction_date", "2026-01-01")
        query.lte.assert_any_call("transaction_date", "2026-06-30")
        query.eq.assert_called_once_with("category", "Food")
        query.gte.assert_any_call("amount", 5.0)
        assert result is query
