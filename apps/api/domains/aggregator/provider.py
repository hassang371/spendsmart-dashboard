# apps/api/domains/aggregator/provider.py
"""Abstract base class for account aggregator providers."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class AggregatorProvider(ABC):
    """Provider interface for account aggregator integrations."""

    @abstractmethod
    async def initiate_consent(self, user_id: str, fi_types: list[str]) -> dict[str, str]:
        """Start consent flow. Returns {redirect_url, consent_id}."""
        ...

    @abstractmethod
    async def check_consent_status(self, consent_id: str) -> dict[str, Any]:
        """Check consent status. Returns {status, detail?}."""
        ...

    @abstractmethod
    async def fetch_transactions(self, consent_id: str, from_date: datetime, to_date: datetime) -> list[dict[str, Any]]:
        """Fetch transactions. Returns normalized transaction dicts."""
        ...

    @abstractmethod
    async def revoke_consent(self, consent_id: str) -> None:
        """Revoke an active consent."""
        ...
