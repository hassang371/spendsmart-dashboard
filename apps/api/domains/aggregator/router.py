# apps/api/domains/aggregator/router.py
"""REST API for account aggregator. Mounted at /api/v1/aggregator/."""

from fastapi import APIRouter, Depends, HTTPException, Response

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.core.config import settings
from apps.api.domains.aggregator import service
from apps.api.domains.aggregator.providers.setu import SetuProvider
from apps.api.domains.aggregator.schemas import BankAccountOut, LinkAccountRequest, LinkAccountResponse, SyncResponse
from supabase import Client

router = APIRouter(prefix="/aggregator", tags=["aggregator"])


def _get_setu_provider() -> SetuProvider:
    if not settings.SETU_CLIENT_ID or not settings.SETU_CLIENT_SECRET:
        raise HTTPException(
            status_code=503,
            detail="Setu provider not configured: SETU_CLIENT_ID and SETU_CLIENT_SECRET must be set in .env",
        )
    return SetuProvider(
        client_id=settings.SETU_CLIENT_ID,
        client_secret=settings.SETU_CLIENT_SECRET,
        base_url=settings.SETU_BASE_URL,
        auth_url=settings.SETU_AUTH_URL,
        product_instance_id=settings.SETU_PRODUCT_INSTANCE_ID,
        redirect_url=settings.SETU_REDIRECT_URL,
    )


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
    return await service.link_account(client, user_id, _get_setu_provider(), body.fi_types, body.vua)


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
