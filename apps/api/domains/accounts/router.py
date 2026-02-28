"""Accounts router — transactions, profile, settings."""

from fastapi import APIRouter, Depends
from supabase import Client

from apps.api.core.auth import get_user_client

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.get("/transactions")
async def list_transactions(client: Client = Depends(get_user_client)):
    """List user's transactions."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    user_id = user_response.user.id
    result = (
        client.table("transactions")
        .select("*")
        .eq("user_id", user_id)
        .order("transaction_date", desc=True)
        .limit(50)
        .execute()
    )
    return {"transactions": result.data, "count": len(result.data)}


@router.get("/profile")
async def get_profile(client: Client = Depends(get_user_client)):
    """Get user profile (stub)."""
    user_response = client.auth.get_user()
    if not user_response or not user_response.user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid bearer token")

    return {
        "id": user_response.user.id,
        "email": user_response.user.email,
    }
