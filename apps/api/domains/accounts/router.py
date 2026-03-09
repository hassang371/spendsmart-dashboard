"""Accounts router — transactions (paginated + filtered), profile, updates.

M2: Upgraded with cursor-based pagination, query filtering, and
typed response models (TransactionOut, ProfileOut).

Frontend Migration: Added PATCH endpoints for transaction updates
and batch reclassification. The frontend no longer writes directly
to Supabase.
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from supabase import Client
from typing import Optional

from apps.api.core.auth import get_current_user, get_current_user_id, get_user_client
from apps.api.core.filtering import TransactionFilter
from apps.api.core.pagination import CursorPage, PaginationParams
from apps.api.domains.accounts.schemas import ProfileOut, TransactionOut
from apps.api.domains.accounts.service import list_user_transactions

router = APIRouter(prefix="/accounts", tags=["accounts"])
logger = structlog.get_logger()


# --- Request schemas ---

def _run_supervised_finetuning_bg(
    user_id: str,
    texts: list[str],
    categories: list[str],
) -> None:
    """Background task: supervised fine-tuning of user's Linear Adapter on corrected transactions.

    Triggered after merchant-batch reclassification. Trains the lightweight
    Linear Adapter (~10KB) on the newly labeled (description, category) pairs.
    The frozen MiniLM base model is never retrained.
    """
    if not texts or len(texts) != len(categories):
        return

    try:
        from packages.categorization.adapter_manager import AdapterManager

        mgr = AdapterManager()
        adapter_state = mgr.fine_tune_supervised(
            texts=texts,
            categories=categories,
            epochs=5,
        )
        if adapter_state:
            mgr.save_user_adapter(user_id, adapter_state)

        logger.info(
            "supervised_finetuning_complete",
            user_id=user_id,
            examples=len(texts),
        )
    except Exception as e:
        logger.warning("supervised_finetuning_failed", user_id=user_id, error=str(e))


def _extract_merchant_keyword(description: str) -> str | None:
    """Extract the most distinctive word from a cleaned transaction description.

    Used to find all related transactions for merchant-batch reclassification.
    Returns None if no keyword with length > 3 is found.
    """
    from packages.categorization.cleaner import clean_description
    from packages.categorization.rules import KeywordMatcher

    matcher = KeywordMatcher()
    cleaned = clean_description(description).lower()
    for keyword in matcher.rules.keys():
        if keyword in cleaned:
            return keyword

    # Fallback: first word with length > 3
    for word in cleaned.split():
        if len(word) > 3:
            return word

    return None


class TransactionUpdate(BaseModel):
    """Updateable fields for a single transaction."""
    category: Optional[str] = Field(default=None, max_length=255, description="New category")
    amount: Optional[float] = Field(default=None, description="New amount (for income flip)")
    old_category: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Previous category — used for merchant-batch reclassification",
    )


class BatchUpdateItem(BaseModel):
    """A single item in a batch update request."""
    id: str = Field(description="Transaction UUID to update")
    category: str = Field(..., max_length=255, description="New category to set")
    amount: Optional[float] = Field(default=None, description="New amount if changed")


class BatchUpdateRequest(BaseModel):
    """Batch update request for reclassifying multiple transactions."""
    updates: list[BatchUpdateItem] = Field(..., max_items=1000, description="List of transactions to update")


@router.get("/transactions")
async def list_transactions(
    limit: int = Query(default=50, ge=1, le=500, description="Items per page"),
    cursor: str = Query(default=None, description="Opaque pagination cursor"),
    include_total: bool = Query(default=False, description="Include total count in response"),
    date_from: str = Query(default=None, description="Filter: start date (ISO 8601)"),
    date_to: str = Query(default=None, description="Filter: end date (ISO 8601)"),
    amount_min: float = Query(default=None, description="Filter: minimum amount"),
    amount_max: float = Query(default=None, description="Filter: maximum amount"),
    category: str = Query(default=None, description="Filter: exact category match"),
    merchant: str = Query(default=None, description="Filter: merchant name (case-insensitive)"),
    type: str = Query(default=None, description="Filter: transaction type (credit/debit)"),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
) -> CursorPage[dict]:
    """List user's transactions with cursor-based pagination and filtering.

    Returns a paginated response with `items`, `next_cursor`, and `has_more`.
    Pass `next_cursor` from a previous response as the `cursor` query param
    to fetch the next page.
    """
    pagination = PaginationParams(
        limit=limit, cursor=cursor, include_total=include_total
    )
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
        user_id=user_id,
        pagination=pagination,
        filters=filters,
    )


@router.get("/transactions/uncategorized")
async def list_uncategorized_transactions(
    limit: int = Query(default=50, ge=1, le=200),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Return transactions where category='Uncategorized', including suggested_category."""

    try:
        res = (
            client.table("transactions")
            .select(
                "id, description, amount, category, suggested_category, "
                "confidence_score, transaction_date, merchant_name, "
                "payment_method, type, created_at, raw_data, "
                "informative_text, bank_name"
            )
            .eq("user_id", user_id)
            .eq("category", "Uncategorized")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"items": res.data or [], "count": len(res.data or [])}
    except Exception as e:
        logger.error("uncategorized_fetch_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch uncategorized transactions")


@router.get("/transactions/count")
async def get_transaction_counts(
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Return total transaction counts split by type (all, debit, credit, uncategorized).

    Uses HEAD requests with count=exact so no row data is transferred.
    """

    try:
        all_res = (
            client.table("transactions")
            .select("*", count="exact", head=True)
            .eq("user_id", user_id)
            .execute()
        )
        debit_res = (
            client.table("transactions")
            .select("*", count="exact", head=True)
            .eq("user_id", user_id)
            .eq("type", "debit")
            .execute()
        )
        uncat_res = (
            client.table("transactions")
            .select("*", count="exact", head=True)
            .eq("user_id", user_id)
            .eq("category", "Uncategorized")
            .execute()
        )
        total = all_res.count or 0
        debit = debit_res.count or 0
        return {
            "all": total,
            "debit": debit,
            "credit": total - debit,
            "uncategorized": uncat_res.count or 0,
        }
    except Exception as e:
        logger.error("transaction_count_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to fetch transaction counts")


@router.patch("/transactions/batch")
async def batch_update_transactions(
    request: BatchUpdateRequest = Body(...),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Batch update multiple transactions (e.g., reclassify similar).

    Replaces the frontend's loop of direct Supabase updates. Each item
    in the batch is updated individually to respect RLS policies.

    NOTE: This route must be registered BEFORE /transactions/{transaction_id}
    so FastAPI matches the literal "batch" path before the dynamic segment.
    """

    if not request.updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    updated = 0
    failed = 0

    # Group items by (category, amount) to collapse N serial round-trips into
    # one Supabase call per unique update payload.
    from collections import defaultdict
    groups: dict[tuple, list[str]] = defaultdict(list)
    for item in request.updates:
        key = (item.category, item.amount)
        groups[key].append(item.id)

    for (category, amount), ids in groups.items():
        try:
            payload: dict = {
                "category": category,
                "is_manual": True,
                "suggested_category": None,
                "confidence_score": None,
            }
            if amount is not None:
                payload["amount"] = amount

            result = (
                client.table("transactions")
                .update(payload)
                .eq("user_id", user_id)
                .in_("id", ids)
                .neq("category", category)
                .execute()
            )
            if result.data:
                updated += len(result.data)
            else:
                failed += len(ids)
        except Exception as e:
            logger.warning("batch_update_group_failed", error=str(e), count=len(ids))
            failed += len(ids)

    return {"status": "ok", "updated": updated, "failed": failed}


@router.patch("/transactions/{transaction_id}")
async def update_transaction(
    background_tasks: BackgroundTasks,
    transaction_id: str = Path(description="Transaction UUID"),
    update: TransactionUpdate = Body(...),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
):
    """Update a single transaction and auto-reclassify all matching merchant transactions.

    When category changes and old_category is provided, all transactions from the
    same merchant that had the old category are automatically updated to the new
    category and marked is_manual=True (merchant-batch reclassification).
    """

    updates: dict = {}
    if update.category is not None:
        updates["category"] = update.category
        updates["is_manual"] = True
        updates["suggested_category"] = None
        updates["confidence_score"] = None
    if update.amount is not None:
        updates["amount"] = update.amount

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

        tx = result.data[0]
        merchant_updated = 0

        # Merchant-batch reclassification: auto-update all matching transactions
        if update.category and update.old_category:
            batch_payload = {
                "category": update.category,
                "is_manual": True,
                "suggested_category": None,
                "confidence_score": None,
            }
            merchant_name = tx.get("merchant_name", "") or ""

            try:
                if merchant_name:
                    # Precise match: same merchant_name
                    batch_result = (
                        client.table("transactions")
                        .update(batch_payload)
                        .eq("user_id", user_id)
                        .eq("category", update.old_category)
                        .eq("merchant_name", merchant_name)
                        .execute()
                    )
                    match_key = f"merchant_name={merchant_name}"
                else:
                    # Fallback: keyword search on description
                    description = tx.get("description", "")
                    keyword = _extract_merchant_keyword(description)
                    if keyword:
                        batch_result = (
                            client.table("transactions")
                            .update(batch_payload)
                            .eq("user_id", user_id)
                            .eq("category", update.old_category)
                            .ilike("description", f"%{keyword}%")
                            .execute()
                        )
                        match_key = f"keyword={keyword}"
                    else:
                        batch_result = None
                        match_key = "none"

                if batch_result:
                    merchant_updated = len(batch_result.data) if batch_result.data else 0
                    logger.info(
                        "merchant_batch_reclassified",
                        match_key=match_key,
                        old=update.old_category,
                        new=update.category,
                        count=merchant_updated,
                    )

                    # Write training_corrections for active learning
                    if merchant_updated > 0 and batch_result.data:
                        for r in batch_result.data:
                            try:
                                client.table("training_corrections").insert({
                                    "user_id": user_id,
                                    "transaction_id": r.get("id"),
                                    "description": r.get("description", ""),
                                    "original_category": update.old_category,
                                    "corrected_category": update.category,
                                }).execute()
                            except Exception:
                                pass

                    # Trigger supervised fine-tuning on the corrected pairs
                    if merchant_updated > 0 and batch_result.data and background_tasks:
                        ft_texts = [
                            r.get("description", "")
                            for r in batch_result.data
                            if r.get("description")
                        ]
                        if ft_texts:
                            ft_categories = [update.category] * len(ft_texts)
                            background_tasks.add_task(
                                _run_supervised_finetuning_bg,
                                user_id,
                                ft_texts,
                                ft_categories,
                            )
            except Exception as e:
                logger.warning("merchant_batch_failed", error=str(e))

        return {
            "status": "ok",
            "transaction": tx,
            "merchant_updated": merchant_updated,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("transaction_update_failed", error=str(e), tx_id=transaction_id)
        raise HTTPException(status_code=500, detail="Failed to update transaction")


@router.get("/profile", response_model=ProfileOut)
async def get_profile(
    current_user=Depends(get_current_user),
) -> ProfileOut:
    """Get user profile."""
    return ProfileOut(
        id=current_user.id,
        email=current_user.email,
    )

