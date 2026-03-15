# apps/api/domains/aggregator/router.py
"""REST API for account aggregator. Mounted at /api/v1/aggregator/."""

import os

from fastapi import APIRouter, Depends, HTTPException, Response

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.domains.aggregator import service
from apps.api.domains.aggregator.providers.setu import SetuProvider
from apps.api.domains.aggregator.schemas import BankAccountOut, LinkAccountRequest, LinkAccountResponse, SyncResponse
from supabase import Client

router = APIRouter(prefix="/aggregator", tags=["aggregator"])


def _get_setu_provider() -> SetuProvider:
    try:
        return SetuProvider(
            client_id=os.environ["SETU_CLIENT_ID"],
            client_secret=os.environ["SETU_CLIENT_SECRET"],
            base_url=os.environ.get("SETU_BASE_URL", "https://fiu-sandbox.setu.co"),
            redirect_url=os.environ.get("SETU_REDIRECT_URL", "http://localhost:3000/dashboard/accounts/callback"),
        )
    except KeyError as e:
        raise HTTPException(status_code=503, detail=f"Provider not configured: missing {e}") from e


@router.get("/accounts/", response_model=list[BankAccountOut])
async def list_accounts(user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)):
    return await service.list_accounts(client, user_id)


@router.get("/accounts/callback")
async def consent_callback(
    consent_id: str, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)
):
    return await service.handle_callback(client, consent_id, _get_setu_provider())


@router.get("/accounts/{account_id}")
async def get_account(
    account_id: str, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)
):
    result = client.table("bank_accounts").select("*").eq("id", account_id).eq("user_id", user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Account not found")
    return result.data[0]


@router.post("/accounts/link", response_model=LinkAccountResponse)
async def link_account(
    body: LinkAccountRequest, user_id: str = Depends(get_current_user_id), client: Client = Depends(get_user_client)
):
    return await service.link_account(client, user_id, _get_setu_provider(), body.fi_types)


@router.post("/accounts/{account_id}/sync", response_model=SyncResponse)
async def sync_account(account_id: str, client: Client = Depends(get_user_client)):
    # Ownership enforced by user-scoped Supabase client (RLS)
    result = await service.sync_account(client, account_id, _get_setu_provider())
    return SyncResponse(account_id=account_id, **result)


@router.delete("/accounts/{account_id}", status_code=204)
async def unlink_account(account_id: str, client: Client = Depends(get_user_client)):
    # Ownership enforced by user-scoped Supabase client (RLS)
    await service.unlink_account(client, account_id, _get_setu_provider())
    return Response(status_code=204)
