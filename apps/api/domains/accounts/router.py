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

from apps.api.core.auth import get_user_client
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
    """Background task: supervised fine-tuning of user adapter on corrected transactions.

    Triggered after merchant-batch reclassification. Trains projector + HypFFN
    on the newly labeled (description, category) pairs.
    """
    if not texts or len(texts) != len(categories):
        return

    try:
        from apps.api.domains.categorization.service import get_classifier
        from packages.categorization.adapter_manager import AdapterManager

        classifier = get_classifier()
        mgr = AdapterManager()

        user_state = mgr.load_user_adapter(user_id)
        if user_state:
            try:
                classifier.load_state_dict(user_state)
            except Exception:
                pass

        mgr.fine_tune_supervised(classifier, texts, categories, epochs=5)
        mgr.save_user_adapter(user_id, classifier.state_dict())

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
    category: Optional[str] = Field(default=None, description="New category")
    amount: Optional[float] = Field(default=None, description="New amount (for income flip)")
    original_category: Optional[str] = Field(
        default=None, description="Backfill original category if missing"
    )
    old_category: Optional[str] = Field(
        default=None,
        description="Previous category — used for merchant-batch reclassification",
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
    background_tasks: BackgroundTasks = None,
    client: Client = Depends(get_user_client),
):
    """Update a single transaction and auto-reclassify all matching merchant transactions.

    When category changes and old_category is provided, all transactions from the
    same merchant that had the old category are automatically updated to the new
    category and marked is_manual=True (merchant-batch reclassification).
    """
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id

    updates: dict = {}
    if update.category is not None:
        updates["category"] = update.category
        updates["is_manual"] = True
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

        tx = result.data[0]
        merchant_updated = 0

        # Merchant-batch reclassification: auto-update all matching transactions
        if update.category and update.old_category:
            description = tx.get("description", "")
            keyword = _extract_merchant_keyword(description)

            if keyword:
                try:
                    batch_result = (
                        client.table("transactions")
                        .update({"category": update.category, "is_manual": True})
                        .eq("user_id", user_id)
                        .eq("category", update.old_category)
                        .ilike("description", f"%{keyword}%")
                        .execute()
                    )
                    merchant_updated = len(batch_result.data) if batch_result.data else 0
                    logger.info(
                        "merchant_batch_reclassified",
                        keyword=keyword,
                        old=update.old_category,
                        new=update.category,
                        count=merchant_updated,
                    )

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
async def get_profile(client: Client = Depends(get_user_client)) -> ProfileOut:
    """Get user profile."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    return ProfileOut(
        id=user_response.user.id,
        email=user_response.user.email,
    )

