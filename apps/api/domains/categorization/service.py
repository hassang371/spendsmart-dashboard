"""Categorization service — singleton classifier access.

Provides a module-level TransactionClassifier singleton and
helper functions for batch/single classification.
"""

from typing import Optional

from supabase import Client

from packages.categorization.classifier import LinearAdapter, TransactionClassifier
from packages.categorization.model_registry import load_latest

_classifier: TransactionClassifier | None = None


def get_classifier() -> TransactionClassifier:
    """Get or create the global TransactionClassifier singleton."""
    global _classifier
    if _classifier is None:
        _classifier = TransactionClassifier()
    return _classifier


def _load_user_adapter(
    clf: TransactionClassifier, client: Client, user_id: str
) -> Optional[LinearAdapter]:
    state_dict = load_latest(client, user_id)
    if not state_dict:
        return None

    adapter = LinearAdapter(
        input_dim=clf.embedding_dim,
        num_classes=len(clf._category_names),
    )
    adapter.load_state_dict(state_dict)
    return adapter


def classify_batch_in_process(
    descriptions: list[str],
    user_id: str | None = None,
    client: Client | None = None,
) -> list[dict]:
    """Classify a batch of transaction descriptions.

    Args:
        descriptions: List of raw transaction description strings.

    Returns:
        List of {"category": str, "confidence": float} dicts.
    """
    clf = get_classifier()
    adapter = None
    if user_id and client:
        adapter = _load_user_adapter(clf, client, user_id)
    return clf.predict_batch(descriptions, adapter=adapter)


def classify_single(
    description: str,
    user_id: str | None = None,
    client: Client | None = None,
) -> dict:
    """Classify a single transaction description.

    Args:
        description: Raw transaction description string.

    Returns:
        {"category": str, "confidence": float}
    """
    clf = get_classifier()
    adapter = None
    if user_id and client:
        adapter = _load_user_adapter(clf, client, user_id)
    return clf.predict(description, adapter=adapter)
