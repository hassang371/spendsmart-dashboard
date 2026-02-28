"""Categorization service — HypCD classifier management and batch inference.

Fixes:
- ARCH-04: Classifier singleton via module-level caching (not per-request).
- BUG-04: In-process batch classification (no N+1 Celery calls).
"""

import os
import threading
import structlog

logger = structlog.get_logger()

# Module-level singleton (thread-safe init)
_classifier = None
_classifier_lock = threading.Lock()


def get_classifier():
    """Get or create the HypCD classifier singleton.

    Fixes ARCH-04: The old code created a new HypCDClassifier() on every
    single request, loading the model from disk each time. This version
    initializes once and reuses.
    """
    global _classifier
    if _classifier is None:
        with _classifier_lock:
            if _classifier is None:  # Double-checked locking
                try:
                    from packages.categorization.hypcd import HypCDClassifier
                    _classifier = HypCDClassifier()
                    logger.info("classifier_initialized", model="HypCDClassifier")
                except Exception as e:
                    logger.error("classifier_init_failed", error=str(e))
                    raise
    return _classifier


def classify_batch_in_process(descriptions: list[str]) -> list[dict]:
    """Classify a batch of descriptions in-process.

    Fixes BUG-04: The old code dispatched a separate Celery task per
    description with .delay().get(timeout=30), causing N+1 Redis round-trips.
    This version runs inference directly — it's fast PyTorch inference,
    no need for Celery.

    Returns list of {category, confidence} dicts.
    """
    classifier = get_classifier()
    predictions = classifier.predict_batch(descriptions)

    results = []
    for pred in predictions:
        if isinstance(pred, dict):
            results.append({
                "category": str(pred.get("category", "Misc")),
                "confidence": float(pred.get("confidence", 0.0)),
            })
        else:
            # Tuple format: (category, confidence, embedding)
            results.append({
                "category": str(pred[0]),
                "confidence": float(pred[1]),
            })
    return results


def classify_single_in_process(description: str) -> dict:
    """Classify a single description in-process."""
    results = classify_batch_in_process([description])
    return results[0] if results else {"category": "Uncategorized", "confidence": 0.0}
