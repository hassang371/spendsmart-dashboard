"""Regression: POST /categorization/feedback must set is_manual=True on transactions.

Bug 4: feedback endpoint only wrote to training_corrections. The training
pipeline reads transactions WHERE is_manual=True — corrections were ignored.

These tests verify the fix lives in CategorizationService.store_feedback()
(the layer responsible since LLD-012 deepening).
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.auth import CurrentUser, get_current_user, get_current_user_id, get_user_client
from apps.api.domains.categorization.router import get_categorization_service, router
from apps.api.domains.categorization.service import CategorizationService, FeedbackResult


class _RecordingService:
    """Stub that records store_feedback calls for assertion."""

    def __init__(self):
        self.calls: list[dict] = []

    def store_feedback(self, corrections, user_id, client) -> FeedbackResult:
        self.calls.append({"corrections": corrections, "user_id": user_id})
        categories = []
        for key, value in corrections.items():
            if isinstance(value, str):
                categories.append(value)
            elif isinstance(value, list):
                categories.append(str(key))
        return FeedbackResult(
            stored_count=sum(1 if isinstance(v, str) else len(v) for v in corrections.values()),
            updated_categories=sorted(set(categories)),
            transaction_sync_failed=False,
        )


@pytest.fixture
def app_with_recording_service():
    recording_service = _RecordingService()
    a = FastAPI()
    a.include_router(router, prefix="/api/v1")
    mock_client = MagicMock()
    a.dependency_overrides[get_user_client] = lambda: mock_client
    a.dependency_overrides[get_current_user_id] = lambda: "uid-1"
    a.dependency_overrides[get_current_user] = lambda: CurrentUser(id="uid-1", email=None)
    a.dependency_overrides[get_categorization_service] = lambda: recording_service
    return a, recording_service


def test_feedback_handler_calls_store_feedback_with_corrections(app_with_recording_service):
    """submit_feedback delegates to service.store_feedback with the corrections dict."""
    app, recording_service = app_with_recording_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/categorization/feedback",
        json={"corrections": {"Swiggy order": "Food", "Uber ride": "Transport"}},
    )

    assert response.status_code == 200
    assert len(recording_service.calls) == 1
    assert recording_service.calls[0]["user_id"] == "uid-1"
    assert "Swiggy order" in recording_service.calls[0]["corrections"]


def test_feedback_calls_store_feedback_for_list_shaped_corrections(app_with_recording_service):
    """List-valued corrections (category → [descriptions]) forwarded to service."""
    app, recording_service = app_with_recording_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/categorization/feedback",
        json={"corrections": {"Food": ["Swiggy order", "Zomato order"]}},
    )

    assert response.status_code == 200
    assert len(recording_service.calls) == 1
    assert "Food" in recording_service.calls[0]["corrections"]


def test_feedback_transactions_update_in_service(fake_classifier=None):
    """CategorizationService.store_feedback writes to transactions table (is_manual=True).

    This is the behavior the original regression guarded — now lives in the service.
    """
    from packages.categorization.classifier import TransactionClassifier

    clf = MagicMock(spec=TransactionClassifier)
    clf.embedding_dim = 384
    clf._category_names = ["Food", "Transport"]
    clf.confidence_threshold = 0.75

    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[])
    update_chain = MagicMock()
    update_chain.eq.return_value = update_chain
    update_chain.execute.return_value = MagicMock(data=[])
    table_mock = MagicMock()
    table_mock.insert.return_value = insert_chain
    table_mock.update.return_value = update_chain
    client_mock = MagicMock()
    client_mock.table.return_value = table_mock

    service = CategorizationService(clf)
    result = service.store_feedback(
        {"Swiggy order": "Food", "Uber ride": "Transport"},
        user_id="uid-1",
        client=client_mock,
    )

    assert result.stored_count == 2
    # Verify transactions table was called for is_manual update
    transactions_calls = [c for c in client_mock.table.call_args_list if c.args and c.args[0] == "transactions"]
    assert len(transactions_calls) >= 2, "Expected one transactions.update() call per correction"
    assert result.transaction_sync_failed is False
