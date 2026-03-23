# apps/worker/sync_task.py
"""Daily auto-sync task for active Account Aggregator bank accounts.

run_auto_sync() is called from the main worker polling loop once every
24 hours. It finds all bank_accounts with consent_status='active' whose
last_synced_at is older than SYNC_INTERVAL_HOURS (or never synced), then
calls service.sync_account() for each, collecting counts and errors.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from apps.api.domains.aggregator import service
from apps.api.domains.aggregator.providers.setu import SetuProvider

logger = logging.getLogger(__name__)

# Accounts that haven't been synced for this many hours are eligible for auto-sync
SYNC_INTERVAL_HOURS = 24


def _get_setu_provider() -> SetuProvider:
    return SetuProvider(
        client_id=os.environ["SETU_CLIENT_ID"],
        client_secret=os.environ["SETU_CLIENT_SECRET"],
        base_url=os.environ.get("SETU_BASE_URL", "https://fiu-sandbox.setu.co"),
        redirect_url=os.environ.get("SETU_REDIRECT_URL", "http://localhost:3000/dashboard/accounts/callback"),
    )


async def run_auto_sync(supabase: Any) -> dict[str, int]:
    """Sync all active AA accounts that haven't been synced in the last 24 hours.

    Uses the service-role Supabase client (bypasses RLS) so the worker can
    access all users' accounts without individual user tokens.

    Returns:
        {"synced": int, "errors": int}
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=SYNC_INTERVAL_HOURS)

    # Fetch all active consent accounts
    result = (
        supabase.table("bank_accounts")
        .select("id, user_id, consent_id, last_synced_at")
        .eq("consent_status", "active")
        .eq("is_manual", False)
        .execute()
    )
    accounts = result.data or []

    synced = 0
    errors = 0

    try:
        provider = _get_setu_provider()
    except KeyError as e:
        logger.error("auto_sync_skipped: Setu provider not configured — missing %s", e)
        return {"synced": 0, "errors": 0}

    for account in accounts:
        last_synced = account.get("last_synced_at")

        # Parse last_synced_at to a timezone-aware datetime for comparison
        if last_synced:
            if isinstance(last_synced, str):
                last_synced_dt = datetime.fromisoformat(last_synced.replace("Z", "+00:00"))
            else:
                last_synced_dt = last_synced
            if last_synced_dt.tzinfo is None:
                last_synced_dt = last_synced_dt.replace(tzinfo=timezone.utc)
            if last_synced_dt >= cutoff:
                # Synced recently enough — skip
                continue

        account_id = account["id"]
        try:
            await service.sync_account(supabase, account_id, provider)
            synced += 1
            logger.info("auto_sync_ok account_id=%s", account_id)
        except Exception as exc:
            errors += 1
            logger.error("auto_sync_failed account_id=%s error=%s", account_id, exc)

    logger.info("auto_sync_complete synced=%d errors=%d", synced, errors)
    return {"synced": synced, "errors": errors}
