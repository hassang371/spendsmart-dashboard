# apps/api/domains/aggregator/providers/manual.py
from datetime import datetime
from typing import Any

from apps.api.domains.aggregator.provider import AggregatorProvider


class ManualProvider(AggregatorProvider):
    async def initiate_consent(self, user_id: str, fi_types: list[str]) -> dict[str, str]:
        raise NotImplementedError("Manual accounts do not use consent flows")

    async def check_consent_status(self, consent_id: str) -> dict[str, Any]:
        return {"status": "none"}

    async def fetch_transactions(self, consent_id: str, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        return []

    async def revoke_consent(self, consent_id: str) -> None:
        pass
