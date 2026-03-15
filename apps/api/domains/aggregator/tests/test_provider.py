# apps/api/domains/aggregator/tests/test_provider.py
"""Tests for AggregatorProvider ABC contract."""

import pytest

from apps.api.domains.aggregator.provider import AggregatorProvider


def test_cannot_instantiate_abstract_provider():
    with pytest.raises(TypeError):
        AggregatorProvider()


def test_concrete_provider_must_implement_all_methods():
    class IncompleteProvider(AggregatorProvider):
        pass

    with pytest.raises(TypeError):
        IncompleteProvider()


def test_concrete_provider_with_all_methods():
    class FakeProvider(AggregatorProvider):
        async def initiate_consent(self, user_id, fi_types):
            return {"redirect_url": "https://example.com", "consent_id": "c1"}

        async def check_consent_status(self, consent_id):
            return {"status": "ACTIVE"}

        async def fetch_transactions(self, consent_id, from_date, to_date):
            return []

        async def revoke_consent(self, consent_id):
            pass

    provider = FakeProvider()
    assert provider is not None
