"""Tests for the v2 TransactionClassifier.

Tests the MiniLM + Cosine Similarity + Linear Adapter classifier.
"""

import pytest
import torch

from packages.categorization.classifier import LinearAdapter, TransactionClassifier
from packages.categorization.constants import Category


@pytest.fixture(scope="module")
def classifier():
    """Module-scoped fixture: loads MiniLM once for all tests."""
    return TransactionClassifier()


# ── Rule-Based Prediction Tests ─────────────────────────────────────────


class TestRuleBasedPrediction:
    """Test that keyword rules fire before the neural network."""

    def test_swiggy_matches_dining_via_rules(self, classifier):
        results = classifier.predict_batch(["Swiggy food delivery"])
        assert len(results) == 1
        assert results[0]["category"] == Category.FOOD.value
        assert results[0]["confidence"] == 1.0

    def test_airbnb_matches_hotels_via_rules(self, classifier):
        results = classifier.predict_batch(["Airbnb accommodation booking"])
        assert len(results) == 1
        assert results[0]["category"] == Category.HOTELS_STAYS.value

    def test_upi_transfer_to_person(self, classifier):
        results = classifier.predict_batch(["UPI Transfer to Allan G via YESB"])
        assert len(results) == 1
        assert results[0]["category"] == Category.TRANSFERS_TO_PEOPLE.value


# ── Cosine Similarity Classification Tests ──────────────────────────────


class TestCosineSimilarity:
    """Test zero-shot classification via cosine similarity."""

    def test_unknown_food_description(self, classifier):
        """An unknown food-related description should classify as a food category."""
        results = classifier.predict_batch(["lunch at local restaurant near office"])
        assert len(results) == 1
        assert results[0]["category"] in [
            Category.FOOD.value,
            Category.COFFEE_SNACKS.value,
            Category.GROCERIES.value,
        ]
        assert 0.0 < results[0]["confidence"] <= 1.0

    def test_unknown_transport_description(self, classifier):
        results = classifier.predict_batch(["cab ride from airport to hotel"])
        assert len(results) == 1
        assert results[0]["category"] in [
            Category.TAXI_RIDESHARE.value,
            Category.PUBLIC_TRANSIT.value,
            Category.FLIGHTS.value,
            Category.TRAVEL_BOOKING.value,
            Category.HOTELS_STAYS.value,
        ]

    def test_confidence_below_threshold_is_uncategorized(self, classifier):
        """Random gibberish should have low confidence."""
        results = classifier.predict_batch(["xyzzy foo baz quux 12345"])
        assert len(results) == 1
        # Low confidence should still return a category (just with low score)
        assert results[0]["confidence"] >= 0.0

    def test_batch_returns_correct_count(self, classifier):
        texts = ["Swiggy order", "Uber ride", "salary credit"]
        results = classifier.predict_batch(texts)
        assert len(results) == 3


# ── Configuration Tests ─────────────────────────────────────────────────


class TestConfiguration:
    """Test classifier configuration."""

    def test_confidence_threshold_default(self, classifier):
        assert classifier.confidence_threshold == 0.75

    def test_embedding_dim(self, classifier):
        assert classifier.embedding_dim == 384


# ── Empty / Edge Case Tests ─────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_batch(self, classifier):
        results = classifier.predict_batch([])
        assert results == []

    def test_empty_string(self, classifier):
        results = classifier.predict_batch([""])
        assert len(results) == 1
        assert results[0]["category"] == Category.UNCATEGORIZED.value

    def test_single_predict(self, classifier):
        result = classifier.predict("Swiggy food order")
        assert result["category"] == Category.FOOD.value


# ── Device Consistency Tests ─────────────────────────────────────────────


def test_train_adapter_moves_adapter_to_embedding_device():
    """Adapter and labels must be on the same device as the embeddings tensor.

    On Apple Silicon, SentenceTransformer auto-selects MPS. Without the fix,
    LinearAdapter is created on CPU, causing a RuntimeError on forward pass.
    This test verifies device co-location regardless of the available hardware.
    """
    clf = TransactionClassifier()
    device = next(clf._model.parameters()).device

    adapter = clf.train_adapter(
        texts=["amazon purchase", "grocery store"],
        categories=["Shopping", "Groceries"],
    )

    # Adapter parameters must live on the same device as the embedding model
    adapter_device = next(adapter.parameters()).device
    assert adapter_device.type == device.type, (
        f"Adapter is on {adapter_device} but embeddings are on {device}. "
        "LinearAdapter must be moved to the embedding device after construction."
    )


def test_adapter_classify_no_device_mismatch():
    """_adapter_classify must move a CPU-resident adapter to the embedding device.

    When an adapter is loaded from storage it arrives on CPU (map_location='cpu').
    If the embedding model is on MPS, calling adapter(embeddings) crashes without
    the explicit .to(embeddings.device) call in _adapter_classify.
    """
    clf = TransactionClassifier()

    # Simulate an adapter loaded from storage — always arrives on CPU
    cpu_adapter = LinearAdapter(clf.embedding_dim, len(clf._category_names))
    # Confirm it really is on CPU before the call
    assert next(cpu_adapter.parameters()).device.type == "cpu"

    # Embeddings will be on whatever device the model chose (CPU, CUDA, or MPS)
    embeddings = clf._model.encode(["grocery purchase"], convert_to_tensor=True)

    # Must not raise RuntimeError regardless of device combination
    results = clf._adapter_classify(embeddings, cpu_adapter)

    assert len(results) == 1
    assert "category" in results[0]
    assert "confidence" in results[0]
    assert isinstance(results[0]["category"], str)
    assert 0.0 <= results[0]["confidence"] <= 1.0
