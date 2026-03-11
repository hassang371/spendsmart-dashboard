"""Tests for cursor-based pagination module.

TDD: These tests define the expected behavior of core/pagination.py
before it exists.
"""

import base64
import json

import pytest

from apps.api.core.pagination import (
    CursorPage,
    PaginationParams,
    decode_cursor,
    encode_cursor,
)


class TestCursorEncoding:
    """Cursor encode/decode roundtrip tests."""

    def test_encode_decode_roundtrip(self):
        """Encoding then decoding a cursor returns the original values."""
        original_date = "2026-01-15T10:30:00+00:00"
        original_id = "abc-123-uuid"
        cursor = encode_cursor(original_date, original_id)
        decoded_date, decoded_id = decode_cursor(cursor)
        assert decoded_date == original_date
        assert decoded_id == original_id

    def test_cursor_is_base64_string(self):
        """Cursor should be a base64-encoded string (opaque to clients)."""
        cursor = encode_cursor("2026-01-15T10:30:00+00:00", "test-id")
        assert isinstance(cursor, str)
        # Should be valid base64
        decoded = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(decoded)
        assert "d" in data  # date
        assert "i" in data  # id

    def test_decode_invalid_cursor_raises(self):
        """Invalid cursor string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor("not-a-valid-cursor!!!")

    def test_decode_empty_cursor_raises(self):
        """Empty cursor string should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid cursor"):
            decode_cursor("")


class TestPaginationParams:
    """Tests for the PaginationParams dependency."""

    def test_default_limit(self):
        """Default limit should be 50."""
        params = PaginationParams()
        assert params.limit == 50

    def test_custom_limit(self):
        """Custom limit should be respected within bounds."""
        params = PaginationParams(limit=25)
        assert params.limit == 25

    def test_max_limit_enforced(self):
        """Limit above 500 should be capped at 500."""
        params = PaginationParams(limit=999)
        assert params.limit == 500

    def test_min_limit_enforced(self):
        """Limit below 1 should be raised to 1."""
        params = PaginationParams(limit=0)
        assert params.limit == 1

    def test_cursor_default_none(self):
        """Cursor should default to None (first page)."""
        params = PaginationParams()
        assert params.cursor is None

    def test_cursor_set(self):
        """Cursor should be stored when provided."""
        params = PaginationParams(cursor="some-cursor")
        assert params.cursor == "some-cursor"


class TestCursorPage:
    """Tests for the CursorPage generic response model."""

    def test_cursor_page_shape(self):
        """CursorPage should have items, next_cursor, and has_more."""
        page = CursorPage(items=[1, 2, 3], next_cursor="abc", has_more=True)
        assert page.items == [1, 2, 3]
        assert page.next_cursor == "abc"
        assert page.has_more is True

    def test_cursor_page_last_page(self):
        """Last page has no next_cursor and has_more=False."""
        page = CursorPage(items=[1], next_cursor=None, has_more=False)
        assert page.next_cursor is None
        assert page.has_more is False

    def test_cursor_page_empty(self):
        """Empty result set is valid."""
        page = CursorPage(items=[], next_cursor=None, has_more=False)
        assert page.items == []
        assert page.has_more is False
