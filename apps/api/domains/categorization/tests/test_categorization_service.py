"""Unit tests for CategorizationService.

Tests exercise the service directly via CategorizationService(fake_classifier) —
no HTTP layer, no monkeypatching of free functions.

Refs: docs/features/012-categorization-service-deepening.md
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.api.domains.categorization.service import (
    CategorizationService,
    ClassificationResult,
    FeedbackResult,
    MetricsResult,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_classifier():
    clf = MagicMock()
    clf.embedding_dim = 384
    clf._category_names = ["Dining", "Taxi & Rideshare", "Subscriptions", "Uncategorized"]
    clf.confidence_threshold = 0.75
    clf.predict.return_value = {"category": "Dining", "confidence": 0.95}
    clf.predict_batch.return_value = [
        {"category": "Dining", "confidence": 0.95},
        {"category": "Taxi & Rideshare", "confidence": 0.90},
    ]
    return clf


@pytest.fixture
def fake_client():
    client = MagicMock()
    table = MagicMock()
    client.table.return_value = table
    table.insert.return_value = table
    table.update.return_value = table
    table.select.return_value = table
    table.eq.return_value = table
    table.execute.return_value = MagicMock(data=[])
    return client


@pytest.fixture
def service(fake_classifier):
    return CategorizationService(fake_classifier)


# ── classify ─────────────────────────────────────────────────────────────────


def test_classify_returns_classification_result(service, fake_client):
    result = service.classify("Swiggy food order", user_id="u1", client=fake_client)
    assert isinstance(result, ClassificationResult)
    assert result.category == "Dining"
    assert result.confidence == 0.95
    assert result.model_used == "minilm-cosine-v2"


def test_classify_calls_predict_with_adapter(service, fake_classifier, fake_client):
    fake_adapter = MagicMock()
    with patch(
        "apps.api.domains.categorization.service._load_adapter",
        return_value=fake_adapter,
    ):
        service.classify("Swiggy food order", user_id="u1", client=fake_client)
    fake_classifier.predict.assert_called_once_with("Swiggy food order", adapter=fake_adapter)


def test_classify_uses_no_adapter_when_load_returns_none(service, fake_classifier, fake_client):
    with patch(
        "apps.api.domains.categorization.service._load_adapter",
        return_value=None,
    ):
        service.classify("unknown txn", user_id="u1", client=fake_client)
    fake_classifier.predict.assert_called_once_with("unknown txn", adapter=None)


# ── classify_batch ────────────────────────────────────────────────────────────


def test_classify_batch_returns_list_of_classification_results(service, fake_client):
    results = service.classify_batch(["Swiggy food", "Uber ride"], user_id="u1", client=fake_client)
    assert len(results) == 2
    assert all(isinstance(r, ClassificationResult) for r in results)
    assert results[0].category == "Dining"
    assert results[1].category == "Taxi & Rideshare"


def test_classify_batch_calls_predict_batch_with_adapter(service, fake_classifier, fake_client):
    fake_adapter = MagicMock()
    with patch(
        "apps.api.domains.categorization.service._load_adapter",
        return_value=fake_adapter,
    ):
        service.classify_batch(["a", "b"], user_id="u1", client=fake_client)
    fake_classifier.predict_batch.assert_called_once_with(["a", "b"], adapter=fake_adapter)


# ── store_feedback ────────────────────────────────────────────────────────────


def test_store_feedback_str_format_inserts_corrections(service, fake_client):
    corrections = {"Swiggy food": "Dining", "Uber ride": "Taxi & Rideshare"}
    result = service.store_feedback(corrections, user_id="u1", client=fake_client)
    assert isinstance(result, FeedbackResult)
    assert result.stored_count == 2
    assert result.transaction_sync_failed is False


def test_store_feedback_list_format_inserts_corrections(service, fake_client):
    corrections = {"Dining": ["Swiggy food", "Zomato order"]}
    result = service.store_feedback(corrections, user_id="u1", client=fake_client)
    assert result.stored_count == 2
    assert "Dining" in result.updated_categories


def test_store_feedback_updated_categories_sorted(service, fake_client):
    corrections = {"Zomato order": "Dining", "Uber ride": "Taxi & Rideshare"}
    result = service.store_feedback(corrections, user_id="u1", client=fake_client)
    assert result.updated_categories == sorted(result.updated_categories)


def test_store_feedback_transaction_sync_failed_on_update_error(service, fake_classifier):
    # Build a client where insert succeeds but update raises.
    insert_chain = MagicMock()
    insert_chain.execute.return_value = MagicMock(data=[])

    update_chain = MagicMock()
    update_chain.execute.side_effect = Exception("DB error")

    table_mock = MagicMock()
    table_mock.insert.return_value = insert_chain
    table_mock.update.return_value = update_chain
    update_chain.eq.return_value = update_chain  # .eq().eq().execute()

    client = MagicMock()
    client.table.return_value = table_mock

    result = service.store_feedback({"Swiggy food": "Dining"}, user_id="u1", client=client)
    assert result.transaction_sync_failed is True
    assert result.stored_count == 1


def test_store_feedback_raises_on_primary_write_failure(service, fake_client):
    fake_client.table.return_value.insert.return_value.execute.side_effect = Exception("primary write failed")
    with pytest.raises(Exception, match="primary write failed"):
        service.store_feedback({"Swiggy food": "Dining"}, user_id="u1", client=fake_client)


def test_store_feedback_empty_corrections_returns_zero(service, fake_client):
    result = service.store_feedback({}, user_id="u1", client=fake_client)
    assert result.stored_count == 0
    assert result.updated_categories == []


# ── compute_metrics ───────────────────────────────────────────────────────────


def test_compute_metrics_returns_metrics_result(service, fake_classifier, fake_client):
    fake_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"description": "Swiggy food", "category": "Dining"},
            {"description": "Uber ride", "category": "Taxi & Rideshare"},
        ]
    )
    fake_classifier.predict_batch.return_value = [
        {"category": "Dining", "confidence": 0.95},
        {"category": "Taxi & Rideshare", "confidence": 0.90},
    ]
    result = service.compute_metrics(user_id="u1", client=fake_client)
    assert isinstance(result, MetricsResult)
    assert result.overall_accuracy == 1.0
    assert result.total_corrections == 2
    assert result.model == "minilm-cosine-v2"
    assert set(result.confidence_histogram.keys()) == {"0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"}


def test_compute_metrics_raises_value_error_on_empty_labeled_data(service, fake_client):
    fake_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[]
    )
    with pytest.raises(ValueError, match="no_labeled_data"):
        service.compute_metrics(user_id="u1", client=fake_client)


def test_compute_metrics_partial_accuracy(service, fake_classifier, fake_client):
    fake_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[
            {"description": "Swiggy food", "category": "Dining"},
            {"description": "Uber ride", "category": "Taxi & Rideshare"},
        ]
    )
    fake_classifier.predict_batch.return_value = [
        {"category": "Dining", "confidence": 0.95},
        {"category": "Dining", "confidence": 0.60},  # wrong prediction
    ]
    result = service.compute_metrics(user_id="u1", client=fake_client)
    assert result.overall_accuracy == 0.5
