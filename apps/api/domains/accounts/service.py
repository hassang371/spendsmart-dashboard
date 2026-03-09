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
from fastapi import HTTPException


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
        .select("*", count="exact" if pagination.include_total else None)
        .eq("user_id", user_id)
    )

    # Apply cursor position if provided
    # True keyset pagination: rows where (transaction_date < cursor_date) OR
    # (transaction_date = cursor_date AND id < cursor_id).
    if pagination.cursor:
        try:
            cursor_date, cursor_id = decode_cursor(pagination.cursor)
        except Exception as e:
            raise HTTPException(status_code=400, detail="Invalid pagination cursor format.")
        query = query.or_(
            f"transaction_date.lt.{cursor_date},"
            f"and(transaction_date.eq.{cursor_date},id.lt.{cursor_id})"
        )

    # Apply user filters
    query = apply_filters(query, filters)

    # Order and limit
    query = (
        query.order("transaction_date", desc=True)
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
        next_cursor = encode_cursor(last["transaction_date"], last["id"])

    total_count = getattr(result, "count", None)
    if not isinstance(total_count, int):
        total_count = None
        
    truncated = (total_count > pagination.limit) if total_count is not None else None

    return CursorPage(
        items=items,
        next_cursor=next_cursor,
        has_more=has_more,
        total_count=total_count,
        truncated=truncated,
    )
