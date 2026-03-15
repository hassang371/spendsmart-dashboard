"""Query filtering module for transaction endpoints.

Provides a reusable TransactionFilter dataclass and apply_filters()
function that chains Supabase query builder calls.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class TransactionFilter:
    """Query parameters for filtering transactions.

    All fields are optional. Non-None fields are AND'd together.

    Usage as FastAPI dependency:
        @router.get("/transactions")
        async def list_tx(filters: TransactionFilter = Depends()):
            ...
    """

    date_from: Optional[str] = None
    date_to: Optional[str] = None
    amount_min: Optional[float] = None
    amount_max: Optional[float] = None
    category: Optional[str] = None
    merchant: Optional[str] = None
    type: Optional[str] = None
    account_id: Optional[str] = None


def apply_filters(query: Any, filters: TransactionFilter) -> Any:
    """Apply non-None filter values to a Supabase query builder.

    Chains .gte(), .lte(), .eq(), .ilike() calls on the query builder
    for each non-None filter field. Returns the (possibly modified) query.

    Args:
        query: A Supabase select query builder instance.
        filters: TransactionFilter with optional filter values.

    Returns:
        The query builder with filter clauses chained.
    """
    if filters.date_from is not None:
        query = query.gte("transaction_date", filters.date_from)
    if filters.date_to is not None:
        query = query.lte("transaction_date", filters.date_to)
    if filters.amount_min is not None:
        query = query.gte("amount", filters.amount_min)
    if filters.amount_max is not None:
        query = query.lte("amount", filters.amount_max)
    if filters.category is not None:
        query = query.eq("category", filters.category)
    if filters.merchant is not None:
        query = query.ilike("merchant_name", f"%{filters.merchant}%")
    if filters.type is not None:
        query = query.eq("type", filters.type)
    if filters.account_id is not None and filters.account_id != "all":
        query = query.eq("account_id", filters.account_id)

    return query
