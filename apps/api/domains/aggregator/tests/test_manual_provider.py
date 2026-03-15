# apps/api/domains/aggregator/tests/test_manual_provider.py
from datetime import datetime, timezone

import pytest

from apps.api.domains.aggregator.providers.manual import ManualProvider


@pytest.fixture
def manual():
    return ManualProvider()


@pytest.mark.asyncio
async def test_initiate_consent_raises(manual):
    with pytest.raises(NotImplementedError, match="Manual accounts do not use consent"):
        await manual.initiate_consent("user-1", ["DEPOSIT"])


@pytest.mark.asyncio
async def test_fetch_transactions_returns_empty(manual):
    result = await manual.fetch_transactions("n/a", datetime.now(timezone.utc), datetime.now(timezone.utc))
    assert result == []


@pytest.mark.asyncio
async def test_revoke_consent_is_noop(manual):
    await manual.revoke_consent("n/a")
