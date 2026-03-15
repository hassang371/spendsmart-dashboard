# apps/api/domains/aggregator/service.py
"""Aggregator service — orchestrates consent, sync, and account lifecycle."""

from datetime import datetime, timezone
from typing import Any

from apps.api.domains.aggregator.provider import AggregatorProvider
from apps.api.domains.ingestion.service import generate_fingerprint


async def list_accounts(client: Any, user_id: str) -> list[dict]:
    return client.table("bank_accounts").select("*").eq("user_id", user_id).order("created_at").execute().data


async def get_or_create_manual_account(client: Any, user_id: str) -> dict:
    existing = client.table("bank_accounts").select("*").eq("user_id", user_id).eq("is_manual", True).execute()
    if existing.data:
        return existing.data[0]
    result = (
        client.table("bank_accounts")
        .insert(
            {
                "user_id": user_id,
                "account_name": "Manual Import",
                "account_type": "manual",
                "is_manual": True,
                "consent_status": "none",
            }
        )
        .execute()
    )
    return result.data[0]


async def link_account(client: Any, user_id: str, provider: AggregatorProvider, fi_types: list[str]) -> dict[str, str]:
    consent = await provider.initiate_consent(user_id, fi_types)
    client.table("bank_accounts").insert(
        {
            "user_id": user_id,
            "account_name": "Linking...",
            "account_type": "savings",
            "provider": "setu",
            "consent_id": consent["consent_id"],
            "consent_status": "pending",
        }
    ).execute()
    return consent


async def handle_callback(client: Any, consent_id: str, provider: AggregatorProvider) -> dict:
    status_result = await provider.check_consent_status(consent_id)
    status = status_result["status"]
    account_row = client.table("bank_accounts").select("*").eq("consent_id", consent_id).execute().data
    if not account_row:
        raise ValueError(f"No account found for consent_id={consent_id}")
    account = account_row[0]

    if status == "ACTIVE":
        detail = status_result.get("detail") or {}
        client.table("bank_accounts").update(
            {
                "consent_status": "active",
                "consent_expiry": detail.get("consentExpiry"),
            }
        ).eq("id", account["id"]).execute()
        return {"account_id": account["id"], "status": "active"}
    elif status == "REJECTED":
        client.table("bank_accounts").delete().eq("id", account["id"]).execute()
        return {"account_id": account["id"], "status": "rejected"}
    else:
        client.table("bank_accounts").update({"consent_status": status.lower()}).eq("id", account["id"]).execute()
        return {"account_id": account["id"], "status": status.lower()}


async def sync_account(client: Any, account_id: str, provider: AggregatorProvider) -> dict[str, int]:
    rows_found = client.table("bank_accounts").select("*").eq("id", account_id).execute().data
    if not rows_found:
        raise ValueError(f"No account found for id={account_id}")
    account = rows_found[0]
    client.table("bank_accounts").update({"sync_status": "syncing"}).eq("id", account_id).execute()

    try:
        from_date = account.get("last_synced_at")
        if from_date and isinstance(from_date, str):
            from_date = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        elif not from_date:
            from_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        to_date = datetime.now(timezone.utc)

        raw_txns = await provider.fetch_transactions(account["consent_id"], from_date, to_date)
        rows = []
        for txn in raw_txns:
            fp = generate_fingerprint(
                date=txn.get("transaction_date", ""),
                amount=txn.get("amount", 0),
                merchant=txn.get("merchant_name", ""),
                description=txn.get("description", ""),
                payment_method=txn.get("payment_method", ""),
                reference=txn.get("reference", ""),
            )
            rows.append(
                {
                    **txn,
                    "user_id": account["user_id"],
                    "account_id": account_id,
                    "fingerprint": fp,
                    "category": "Uncategorized",
                }
            )

        inserted = 0
        if rows:
            result = client.rpc(
                "batch_import_transactions",
                {
                    "p_user_id": account["user_id"],
                    "p_account_id": account_id,
                    "p_rows": rows,
                },
            ).execute()
            if result.data:
                row = result.data[0] if isinstance(result.data, list) else result.data
                if isinstance(row, dict):
                    inserted = int(row.get("inserted_count", 0))
                else:
                    inserted = len(rows)  # unexpected shape: assume all inserted, skipped=0

        client.table("bank_accounts").update(
            {
                "sync_status": "idle",
                "last_synced_at": to_date.isoformat(),
            }
        ).eq("id", account_id).execute()
        return {"inserted": inserted, "skipped_duplicates": len(rows) - inserted}
    except Exception:
        client.table("bank_accounts").update({"sync_status": "error"}).eq("id", account_id).execute()
        raise


async def unlink_account(client: Any, account_id: str, provider: AggregatorProvider) -> None:
    account = client.table("bank_accounts").select("*").eq("id", account_id).execute().data[0]
    if account["is_manual"]:
        raise ValueError("Cannot unlink Manual Import account")
    if account.get("consent_id") and account["consent_status"] == "active":
        await provider.revoke_consent(account["consent_id"])
    client.table("bank_accounts").update({"consent_status": "revoked", "sync_status": "idle"}).eq(
        "id", account_id
    ).execute()
