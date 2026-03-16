# apps/api/domains/aggregator/providers/setu.py
"""Setu Account Aggregator provider implementation.

Auth flow (v2):
  1. POST client_credentials to Keycloak token endpoint → Bearer JWT
  2. Use Bearer token + x-product-instance-id in all FIU API calls
  3. FIU endpoints live under /v2/ path prefix
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException

from apps.api.domains.aggregator.provider import AggregatorProvider

logger = logging.getLogger(__name__)


def _handle_setu_error(exc: httpx.HTTPStatusError | httpx.RequestError, operation: str) -> None:
    """Convert httpx errors into FastAPI HTTPException.

    Without this, unhandled httpx exceptions propagate through the
    middleware stack and bypass Starlette's CORSMiddleware response
    path, stripping Access-Control-Allow-Origin headers from the
    error response. The browser then reports a CORS error instead
    of showing the real problem.
    """
    if isinstance(exc, httpx.RequestError) and not isinstance(exc, httpx.HTTPStatusError):
        logger.error("setu_%s_request_failed error=%s", operation, str(exc))
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Setu API during {operation}: {type(exc).__name__}",
        ) from exc

    body = exc.response.text
    status = exc.response.status_code
    logger.error("setu_%s_failed status=%s body=%s", operation, status, body)

    try:
        detail = exc.response.json().get("message", body)
    except Exception:
        detail = body

    if status == 401:
        raise HTTPException(
            status_code=502,
            detail=f"Setu authentication failed: {detail}. Check SETU_CLIENT_ID and SETU_CLIENT_SECRET in .env",
        ) from exc
    elif status == 400:
        raise HTTPException(
            status_code=400,
            detail=f"Setu rejected the request: {detail}",
        ) from exc
    else:
        raise HTTPException(
            status_code=502,
            detail=f"Setu API error during {operation}: {status} — {detail}",
        ) from exc


class SetuProvider(AggregatorProvider):
    """Setu Data Gateway AA integration (v2 OAuth2 Bearer flow).

    Accepts optional http_client for dependency injection (testing).
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        redirect_url: str,
        auth_url: str = "https://auth-v2.setu.co/realms/setu/protocol/openid-connect/token",
        product_instance_id: str = "",
        http_client: httpx.AsyncClient | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.auth_url = auth_url
        self.product_instance_id = product_instance_id
        self.redirect_url = redirect_url
        self._http_client: httpx.AsyncClient = http_client or httpx.AsyncClient(timeout=30.0)

        # Cached token + expiry
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    async def _get_token(self) -> str:
        """Obtain or return a cached Bearer token via OAuth2 client_credentials."""
        # Return cached token if still valid (with 60s buffer)
        if self._access_token and time.time() < (self._token_expires_at - 60):
            return self._access_token

        client = self._client()
        resp = await client.post(
            self.auth_url,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _handle_setu_error(exc, "auth_token")
        except httpx.RequestError as exc:
            _handle_setu_error(exc, "auth_token")

        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 1800)
        logger.info("setu_token_refreshed expires_in=%s", data.get("expires_in"))
        return self._access_token

    async def _headers(self) -> dict[str, str]:
        """Build headers with Bearer auth and product instance ID."""
        token = await self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if self.product_instance_id:
            headers["x-product-instance-id"] = self.product_instance_id
        return headers

    def _client(self) -> httpx.AsyncClient:
        return self._http_client

    async def initiate_consent(self, user_id: str, fi_types: list[str]) -> dict[str, str]:
        now = datetime.now(timezone.utc)
        payload = {
            "consentDuration": {"unit": "MONTH", "value": "12"},
            "vua": user_id,
            "dataRange": {
                "from": (now - timedelta(days=365)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "context": [],
            "redirectUrl": self.redirect_url,
        }
        client = self._client()
        headers = await self._headers()
        resp = await client.post(f"{self.base_url}/v2/consents", json=payload, headers=headers)
        logger.info(
            "setu_consent_response status=%s body=%s",
            resp.status_code,
            resp.text,
        )
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _handle_setu_error(exc, "initiate_consent")
        except httpx.RequestError as exc:
            _handle_setu_error(exc, "initiate_consent")
        data = resp.json()
        return {"consent_id": data["id"], "redirect_url": data["url"]}

    async def check_consent_status(self, consent_id: str) -> dict[str, Any]:
        client = self._client()
        headers = await self._headers()
        resp = await client.get(f"{self.base_url}/v2/consents/{consent_id}", headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _handle_setu_error(exc, "check_consent_status")
        except httpx.RequestError as exc:
            _handle_setu_error(exc, "check_consent_status")
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
        headers = await self._headers()
        resp = await client.post(f"{self.base_url}/v2/fi/fetch", json=payload, headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _handle_setu_error(exc, "fetch_transactions")
        except httpx.RequestError as exc:
            _handle_setu_error(exc, "fetch_transactions")
        return self._normalize_transactions(resp.json())

    async def revoke_consent(self, consent_id: str) -> None:
        client = self._client()
        headers = await self._headers()
        resp = await client.post(f"{self.base_url}/v2/consents/{consent_id}/revoke", headers=headers)
        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _handle_setu_error(exc, "revoke_consent")
        except httpx.RequestError as exc:
            _handle_setu_error(exc, "revoke_consent")

    def _normalize_transactions(self, setu_response: dict[str, Any]) -> list[dict[str, Any]]:
        transactions = []
        for fi in setu_response.get("fi", []):
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
                        "bank_name": "",
                        "raw_data": txn,
                    }
                )
        return transactions
