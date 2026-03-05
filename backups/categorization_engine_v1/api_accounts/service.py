"""Accounts service — user transaction queries with pagination and filtering.

Service layer handles query construction, keeping the router thin.
"""

from typing import Any, Optional

from apps.api.core.filtering import TransactionFilter, apply_filters
from apps.api.core.pagination import (
    CursorPage,
    PaginationParams,
    decode_cursor,
    encode_cursor,
)


def list_user_transactions(
    client: Any,
    user_id: str,
    pagination: PaginationParams,
    filters: TransactionFilter,
) -> CursorPage[dict]:
    """Query user transactions with cursor-based pagination and filtering.

    Fetches limit+1 rows to determine has_more, then trims to limit.

    Args:
        client: Supabase client instance.
        user_id: Authenticated user's UUID.
        pagination: Pagination parameters (limit, cursor).
        filters: Optional filter criteria.

    Returns:
        CursorPage with items, next_cursor, and has_more.
    """
    fetch_limit = pagination.limit + 1  # Fetch one extra to detect more pages

    query = (
        client.table("transactions")
        .select("*")
        .eq("user_id", user_id)
    )

    # Apply cursor position if provided
    # True keyset pagination: rows where (created_at < cursor_date) OR
    # (created_at = cursor_date AND id < cursor_id).
    # This handles batch-imported transactions with identical timestamps correctly.
    if pagination.cursor:
        cursor_date, cursor_id = decode_cursor(pagination.cursor)
        query = query.or_(
            f"created_at.lt.{cursor_date},"
            f"and(created_at.eq.{cursor_date},id.lt.{cursor_id})"
        )

    # Apply user filters
    query = apply_filters(query, filters)

    # Order and limit
    query = (
        query.order("created_at", desc=True)
        .order("id", desc=True)
        .limit(fetch_limit)
    )

    result = query.execute()
    rows = result.data

    # Determine if there are more pages
    has_more = len(rows) > pagination.limit
    items = rows[: pagination.limit]

    # Build next cursor from the last item
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = encode_cursor(last["created_at"], last["id"])

    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)
