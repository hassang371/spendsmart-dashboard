# apps/api/domains/aggregator/providers/setu.py
"""Setu Account Aggregator provider implementation."""

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from apps.api.domains.aggregator.provider import AggregatorProvider


class SetuProvider(AggregatorProvider):
    """Setu Data Gateway AA integration.

    Accepts optional http_client for dependency injection (testing).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        redirect_url: str,
        http_client: httpx.AsyncClient | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.redirect_url = redirect_url
        # Reuse a single client instance to avoid per-request connection leaks
        self._http_client: httpx.AsyncClient = http_client or httpx.AsyncClient()

    def _headers(self) -> dict[str, str]:
        return {
            "x-client-id": self.client_id,
            "x-client-secret": self.client_secret,
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return self._http_client

    async def initiate_consent(self, user_id: str, fi_types: list[str]) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        payload = {
            "Detail": {
                "consentStart": now.isoformat(),
                "consentExpiry": (now + timedelta(days=365)).isoformat(),
                "fiTypes": fi_types,
                "consentTypes": ["TRANSACTIONS"],
                "fetchType": "PERIODIC",
                "Frequency": {"value": 1, "unit": "DAY"},
                "DataLife": {"value": 1, "unit": "YEAR"},
            },
            "redirectUrl": self.redirect_url,
        }
        client = self._client()
        resp = await client.post(f"{self.base_url}/consents", json=payload, headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return {"consent_id": data["id"], "redirect_url": data["url"]}

    async def check_consent_status(self, consent_id: str) -> dict[str, Any]:
        client = self._client()
        resp = await client.get(f"{self.base_url}/consents/{consent_id}", headers=self._headers())
        resp.raise_for_status()
        data = resp.json()
        return {"status": data["status"], "detail": data.get("detail")}

    async def fetch_transactions(self, consent_id: str, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        payload = {
            "consentId": consent_id,
            "DataRange": {
                "from": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": to_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "format": "json",
        }
        client = self._client()
        resp = await client.post(f"{self.base_url}/fi/fetch", json=payload, headers=self._headers())
        resp.raise_for_status()
        return self._normalize_transactions(resp.json())

    async def revoke_consent(self, consent_id: str) -> None:
        client = self._client()
        resp = await client.post(f"{self.base_url}/consents/{consent_id}/revoke", headers=self._headers())
        resp.raise_for_status()

    def _normalize_transactions(self, setu_response: dict[str, Any]) -> list[dict[str, Any]]:
        transactions = []
        for fi in setu_response.get("fi", []):
            account_data = fi.get("data", {}).get("account", {})
            for txn in fi.get("data", {}).get("transactions", []):
                amount = float(txn["amount"])
                amount = -abs(amount) if txn.get("type") == "DEBIT" else abs(amount)
                transactions.append(
                    {
                        "transaction_date": txn["transactionTimestamp"][:19],
                        "amount": amount,
                        "description": txn.get("narration", ""),
                        "merchant_name": "",
                        "payment_method": txn.get("mode", ""),
                        "type": txn.get("type", "").lower(),
                        "status": "completed",
                        "currency": "INR",
                        "reference": txn.get("reference", ""),
                        "bank_name": "",  # Setu response doesn't include bank name directly
                        "raw_data": txn,
                    }
                )
        return transactions
