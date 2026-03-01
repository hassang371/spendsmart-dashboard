"""Accounts router — transactions (paginated + filtered), profile, updates.

M2: Upgraded with cursor-based pagination, query filtering, and
typed response models (TransactionOut, ProfileOut).

Frontend Migration: Added PATCH endpoints for transaction updates
and batch reclassification. The frontend no longer writes directly
to Supabase.
"""

import structlog
from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from supabase import Client
from typing import Optional

from apps.api.core.auth import get_user_client
from apps.api.core.filtering import TransactionFilter
from apps.api.core.pagination import CursorPage, PaginationParams
from apps.api.domains.accounts.schemas import ProfileOut, TransactionOut
from apps.api.domains.accounts.service import list_user_transactions

router = APIRouter(prefix="/accounts", tags=["accounts"])
logger = structlog.get_logger()


# --- Request schemas ---

class TransactionUpdate(BaseModel):
    """Updateable fields for a single transaction."""
    category: Optional[str] = Field(default=None, description="New category")
    amount: Optional[float] = Field(default=None, description="New amount (for income flip)")
    original_category: Optional[str] = Field(
        default=None, description="Backfill original category if missing"
    )


class BatchUpdateItem(BaseModel):
    """A single item in a batch update request."""
    id: str = Field(description="Transaction UUID to update")
    category: str = Field(description="New category to set")
    amount: Optional[float] = Field(default=None, description="New amount if changed")


class BatchUpdateRequest(BaseModel):
    """Batch update request for reclassifying multiple transactions."""
    updates: list[BatchUpdateItem] = Field(description="List of transactions to update")


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


@router.patch("/transactions/batch")
async def batch_update_transactions(
    request: BatchUpdateRequest = Body(...),
    client: Client = Depends(get_user_client),
):
    """Batch update multiple transactions (e.g., reclassify similar).

    Replaces the frontend's loop of direct Supabase updates. Each item
    in the batch is updated individually to respect RLS policies.

    NOTE: This route must be registered BEFORE /transactions/{transaction_id}
    so FastAPI matches the literal "batch" path before the dynamic segment.
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id

    if not request.updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updated = 0
    failed = 0
    for item in request.updates:
        try:
            updates: dict = {"category": item.category}
            if item.amount is not None:
                updates["amount"] = item.amount

            result = (
                client.table("transactions")
                .update(updates)
                .eq("id", item.id)
                .eq("user_id", user_id)
                .execute()
            )
            if result.data:
                updated += 1
            else:
                failed += 1
        except Exception as e:
            logger.warning("batch_update_item_failed", error=str(e), tx_id=item.id)
            failed += 1

    return {"status": "ok", "updated": updated, "failed": failed}


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    transaction_id: str = Path(description="Transaction UUID"),
    update: TransactionUpdate = Body(...),
    client: Client = Depends(get_user_client),
):
    """Update a single transaction (category, amount, etc.).

    Replaces the frontend's direct `supabase.from('transactions').update(...)`.
    Handles income auto-flip: when category changes to/from 'Income',
    the amount sign is automatically adjusted.
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id

    # Build update dict (only non-None fields)
    updates = {}
    if update.category is not None:
        updates["category"] = update.category
    if update.amount is not None:
        updates["amount"] = update.amount
    if update.original_category is not None:
        updates["original_category"] = update.original_category

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        result = (
            client.table("transactions")
            .update(updates)
            .eq("id", transaction_id)
            .eq("user_id", user_id)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Transaction not found")

        return {"status": "ok", "transaction": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("transaction_update_failed", error=str(e), tx_id=transaction_id)
        raise HTTPException(status_code=500, detail="Failed to update transaction")


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

