"""Accounts router — transactions (paginated + filtered), profile.

M2: Upgraded with cursor-based pagination, query filtering, and
typed response models (TransactionOut, ProfileOut).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from apps.api.core.auth import get_user_client
from apps.api.core.filtering import TransactionFilter
from apps.api.core.pagination import CursorPage, PaginationParams
from apps.api.domains.accounts.schemas import ProfileOut, TransactionOut
from apps.api.domains.accounts.service import list_user_transactions

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/transactions")
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=100, description="Items per page"),
    cursor: str = Query(default=None, description="Opaque pagination cursor"),
    date_from: str = Query(default=None, description="Filter: start date (ISO 8601)"),
    date_to: str = Query(default=None, description="Filter: end date (ISO 8601)"),
    amount_min: float = Query(default=None, description="Filter: minimum amount"),
    amount_max: float = Query(default=None, description="Filter: maximum amount"),
    category: str = Query(default=None, description="Filter: exact category match"),
    merchant: str = Query(default=None, description="Filter: merchant name (case-insensitive)"),
    type: str = Query(default=None, description="Filter: transaction type (credit/debit)"),
    client: Client = Depends(get_user_client),
) -> CursorPage[dict]:
    """List user's transactions with cursor-based pagination and filtering.

    Returns a paginated response with `items`, `next_cursor`, and `has_more`.
    Pass `next_cursor` from a previous response as the `cursor` query param
    to fetch the next page.
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    pagination = PaginationParams(limit=limit, cursor=cursor)
    filters = TransactionFilter(
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        category=category,
        merchant=merchant,
        type=type,
    )

    return list_user_transactions(
        client=client,
        user_id=user_response.user.id,
        pagination=pagination,
        filters=filters,
    )


@router.get("/profile", response_model=ProfileOut)
async def get_profile(client: Client = Depends(get_user_client)) -> ProfileOut:
    """Get user profile."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    return ProfileOut(
        id=user_response.user.id,
        email=user_response.user.email,
    )
