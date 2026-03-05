"""Categorization service — singleton classifier access.

Provides a module-level TransactionClassifier singleton and
helper functions for batch/single classification.
"""

from packages.categorization.classifier import TransactionClassifier

_classifier: TransactionClassifier | None = None


def get_classifier() -> TransactionClassifier:
    """Get or create the global TransactionClassifier singleton."""
    global _classifier
    if _classifier is None:
        _classifier = TransactionClassifier()
    return _classifier


def classify_batch_in_process(descriptions: list[str]) -> list[dict]:
    """Classify a batch of transaction descriptions.

    Args:
        descriptions: List of raw transaction description strings.

    Returns:
        List of {"category": str, "confidence": float} dicts.
    """
    clf = get_classifier()
    return clf.predict_batch(descriptions)


def classify_single(description: str) -> dict:
    """Classify a single transaction description.

    Args:
        description: Raw transaction description string.

    Returns:
        {"category": str, "confidence": float}
    """
    clf = get_classifier()
    return clf.predict(description)
