"""FastAPI dependencies for authentication.

Extracts the user's JWT from the Authorization header and provides
a Supabase client scoped to that user for RLS-enforced queries.
"""
from fastapi import Depends, Header, HTTPException
from supabase import Client

from apps.api.supabase_client import get_supabase_client


async def get_user_token(authorization: str = Header(default="")) -> str:
    """
    Extract Bearer token from Authorization header.
    Returns the raw JWT string.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Expected: Bearer <token>",
        )

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing bearer token",
        )
    return token


async def get_user_client(token: str = Depends(get_user_token)) -> Client:
    """
    Provides a Supabase client authenticated with the user's JWT.
    RLS policies will be enforced for all queries.
    """
    return get_supabase_client(access_token=token)
