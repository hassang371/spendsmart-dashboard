"""Categorization service — deep module owning all categorization behavior.

Refs: docs/features/012-categorization-service-deepening.md
"""

from __future__ import annotations

from dataclasses import dataclass, field

try:
    import structlog

    logger = structlog.get_logger()
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from typing import Optional

from packages.categorization.classifier import LinearAdapter, TransactionClassifier
from packages.categorization.model_registry import load_latest
from supabase import Client

# ── Result types ──────────────────────────────────────────────────────────────


@dataclass
class ClassificationResult:
    category: str
    confidence: float
    model_used: str = "minilm-cosine-v2"


@dataclass
class FeedbackResult:
    stored_count: int
    updated_categories: list[str]
    transaction_sync_failed: bool = False


@dataclass
class MetricsResult:
    overall_accuracy: float
    confidence_histogram: dict[str, int]
    total_corrections: int
    model: str = "minilm-cosine-v2"


# ── Shared classifier singleton ───────────────────────────────────────────────
# Background tasks (e.g. accounts adapter fine-tuning) need direct access to
# the TransactionClassifier without going through the FastAPI app.state.
# get_classifier() returns the same instance that CategorizationService uses.

_classifier: TransactionClassifier | None = None


def get_classifier() -> TransactionClassifier:
    global _classifier
    if _classifier is None:
        _classifier = TransactionClassifier()
    return _classifier


# ── Internal helpers ──────────────────────────────────────────────────────────


def _load_adapter(clf: TransactionClassifier, client: Client, user_id: str) -> Optional[LinearAdapter]:
    state_dict = load_latest(client, user_id)
    if not state_dict:
        return None
    adapter = LinearAdapter(
        input_dim=clf.embedding_dim,
        num_classes=len(clf._category_names),
    )
    adapter.load_state_dict(state_dict)
    return adapter


def _build_correction_rows(corrections: dict[str, str | list[str]], user_id: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in corrections.items():
        if isinstance(value, str):
            rows.append({"user_id": user_id, "description": str(key), "corrected_category": value})
        elif isinstance(value, list):
            for description in value:
                rows.append({"user_id": user_id, "description": str(description), "corrected_category": str(key)})
    return rows


# ── Backward-compat helpers (used by ingestion router) ───────────────────────
# Ingestion calls classify_batch_in_process without user context (no adapter).


def classify_batch_in_process(
    descriptions: list[str],
    user_id: str | None = None,
    client: Client | None = None,
) -> list[dict]:
    clf = get_classifier()
    return clf.predict_batch(descriptions)


# ── Service ───────────────────────────────────────────────────────────────────


class CategorizationService:
    def __init__(self, classifier: TransactionClassifier) -> None:
        self._clf = classifier

    # -- Classification --------------------------------------------------------

    def classify(self, description: str, user_id: str, client: Client) -> ClassificationResult:
        adapter = _load_adapter(self._clf, client, user_id)
        result = self._clf.predict(description, adapter=adapter)
        return ClassificationResult(category=result["category"], confidence=result["confidence"])

    def classify_batch(self, descriptions: list[str], user_id: str, client: Client) -> list[ClassificationResult]:
        adapter = _load_adapter(self._clf, client, user_id)
        results = self._clf.predict_batch(descriptions, adapter=adapter)
        return [ClassificationResult(category=r["category"], confidence=r["confidence"]) for r in results]

    # -- Feedback --------------------------------------------------------------

    def store_feedback(
        self,
        corrections: dict[str, str | list[str]],
        user_id: str,
        client: Client,
    ) -> FeedbackResult:
        rows = _build_correction_rows(corrections, user_id)
        if not rows:
            return FeedbackResult(stored_count=0, updated_categories=[])

        # Primary write — fatal on failure.
        client.table("training_corrections").insert(rows).execute()

        # Denormalization write — non-fatal; failure surfaced in result.
        transaction_sync_failed = False
        for row in rows:
            try:
                (
                    client.table("transactions")
                    .update({"is_manual": True, "category": row["corrected_category"]})
                    .eq("user_id", user_id)
                    .eq("description", row["description"])
                    .execute()
                )
            except Exception as e:
                transaction_sync_failed = True
                logger.warning(
                    "feedback_transaction_sync_failed",
                    description=row["description"],
                    error=str(e),
                )

        updated_categories = sorted({row["corrected_category"] for row in rows if row["corrected_category"]})
        return FeedbackResult(
            stored_count=len(rows),
            updated_categories=updated_categories,
            transaction_sync_failed=transaction_sync_failed,
        )

    # -- Metrics ---------------------------------------------------------------

    def compute_metrics(self, user_id: str, client: Client) -> MetricsResult:
        result = (
            client.table("transactions")
            .select("description,category")
            .eq("user_id", user_id)
            .eq("is_manual", True)
            .execute()
        )
        labeled = result.data or []
        if not labeled:
            raise ValueError("no_labeled_data")

        descriptions = [r["description"] for r in labeled if r.get("description")]
        true_categories = [r["category"] for r in labeled if r.get("description")]

        adapter = _load_adapter(self._clf, client, user_id)
        predictions = self._clf.predict_batch(descriptions, adapter=adapter)
        pred_categories = [p["category"] for p in predictions]
        confidences = [p["confidence"] for p in predictions]

        correct = sum(1 for t, p in zip(true_categories, pred_categories) if t == p)
        accuracy = round(correct / len(true_categories), 4) if true_categories else 0.0

        bucket_keys = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
        buckets: dict[str, int] = {k: 0 for k in bucket_keys}
        for c in confidences:
            idx = min(int(c / 0.2), 4)
            buckets[bucket_keys[idx]] += 1

        return MetricsResult(
            overall_accuracy=accuracy,
            confidence_histogram=buckets,
            total_corrections=len(labeled),
        )

    # -- Model info ------------------------------------------------------------

    @property
    def confidence_threshold(self) -> float:
        return self._clf.confidence_threshold
