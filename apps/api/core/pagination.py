"""Cursor-based (keyset) pagination module.

Provides reusable pagination primitives for all collection endpoints.
Uses cursor-based pagination instead of OFFSET for O(1) page fetch
regardless of dataset size.

The cursor is an opaque base64-encoded JSON string containing the
sort key values (created_at, id) from the last item on the current page.
"""

import base64
import json
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorPage(BaseModel, Generic[T]):
    """Generic paginated response using cursor-based pagination."""

    items: list[T] = Field(description="List of items in this page")
    next_cursor: Optional[str] = Field(
        default=None,
        description="Opaque cursor to pass as `cursor` for the next page. "
        "Null when there are no more pages.",
    )
    has_more: bool = Field(
        description="Whether there are more items after this page"
    )


class PaginationParams:
    """FastAPI dependency for pagination query parameters.

    Usage:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            ...
    """

    def __init__(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
    ):
        self.limit = max(1, min(limit, 500))  # Clamp to [1, 500]
        self.cursor = cursor


def encode_cursor(created_at: str, item_id: str) -> str:
    """Encode pagination cursor from sort key values.

    Args:
        created_at: ISO 8601 timestamp string of the last item.
        item_id: UUID string of the last item.

    Returns:
        URL-safe base64-encoded cursor string.
    """
    payload = json.dumps({"d": created_at, "i": item_id}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, str]:
    """Decode a pagination cursor into sort key values.

    Args:
        cursor: The opaque cursor string from the client.

    Returns:
        Tuple of (created_at, item_id).

    Raises:
        ValueError: If the cursor is malformed.
    """
    if not cursor:
        raise ValueError("Invalid cursor: empty string")
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(decoded)
        return data["d"], data["i"]
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc
