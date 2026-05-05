"""Integration tests for the categorization API endpoints.

Tests the HTTP layer via TestClient. CategorizationService injected via
dependency override — no monkeypatching of free functions.

Refs: docs/features/012-categorization-service-deepening.md
"""

from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.core.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_user_client,
)
from apps.api.domains.categorization.router import get_categorization_service, router
from apps.api.domains.categorization.service import (
    CategorizationService,
    ClassificationResult,
    FeedbackResult,
    MetricsResult,
)

# ── Stub service ──────────────────────────────────────────────────────────────


class _StubCategorizationService:
    """Minimal stub — returns deterministic results without loading MiniLM."""

    confidence_threshold = 0.75

    def classify(self, description: str, user_id: str, client) -> ClassificationResult:
        upper = description.upper()
        if "UBER" in upper:
            return ClassificationResult(category="Taxi & Rideshare", confidence=0.9)
        if "ZOMATO" in upper or "SWIGGY" in upper:
            return ClassificationResult(category="Dining", confidence=0.95)
        if "NETFLIX" in upper:
            return ClassificationResult(category="Subscriptions", confidence=0.88)
        return ClassificationResult(category="Uncategorized", confidence=0.3)

    def classify_batch(self, descriptions: list[str], user_id: str, client) -> list[ClassificationResult]:
        return [self.classify(d, user_id, client) for d in descriptions]

    def store_feedback(self, corrections, user_id: str, client) -> FeedbackResult:
        rows = []
        for key, value in corrections.items():
            if isinstance(value, str):
                rows.append({"corrected_category": value})
            elif isinstance(value, list):
                rows.extend([{"corrected_category": str(key)} for _ in value])
        categories = sorted({r["corrected_category"] for r in rows})
        return FeedbackResult(
            stored_count=len(rows),
            updated_categories=categories,
            transaction_sync_failed=False,
        )

    def compute_metrics(self, user_id: str, client) -> MetricsResult:
        return MetricsResult(
            overall_accuracy=0.85,
            confidence_histogram={"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 1, "0.8-1.0": 2},
            total_corrections=3,
        )


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def app():
    a = FastAPI()
    a.include_router(router, prefix="/api/v1")
    return a


@pytest.fixture
def mock_user_client():
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_client.auth.get_user.return_value = MagicMock(user=mock_user)
    return mock_client


@pytest.fixture
def client(app, mock_user_client):
    stub_service = _StubCategorizationService()
    app.dependency_overrides[get_user_client] = lambda: mock_user_client
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-id", email=None)
    app.dependency_overrides[get_categorization_service] = lambda: stub_service
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# ── /classify/batch ───────────────────────────────────────────────────────────


def test_batch_classify_returns_predictions(client):
    payload = {
        "descriptions": [
            "Uber trip to airport",
            "Swiggy food order",
            "Random unknown store",
        ]
    }
    response = client.post("/api/v1/categorization/classify/batch", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "predictions" in data
    assert len(data["predictions"]) == 3
    assert data["predictions"][0]["category"] == "Taxi & Rideshare"
    assert data["predictions"][1]["category"] == "Dining"
    assert data["predictions"][2]["category"] == "Uncategorized"


def test_batch_classify_empty_descriptions(client):
    response = client.post("/api/v1/categorization/classify/batch", json={"descriptions": []})
    assert response.status_code == 400


def test_batch_classify_missing_field(client):
    response = client.post("/api/v1/categorization/classify/batch", json={"texts": ["something"]})
    assert response.status_code == 422


# ── /classify ─────────────────────────────────────────────────────────────────


def test_single_classify_food(client):
    response = client.post(
        "/api/v1/categorization/classify",
        json={"description": "Swiggy food order"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Dining"
    assert data["model_used"] == "minilm-cosine-v2"


def test_single_classify_unknown(client):
    response = client.post(
        "/api/v1/categorization/classify",
        json={"description": "Random store purchase"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Uncategorized"


# ── /feedback ─────────────────────────────────────────────────────────────────


def test_feedback_accepts_corrections(client):
    payload = {
        "corrections": {
            "Dining": ["Uber Eats delivery"],
            "Taxi & Rideshare": ["Ola cab ride"],
        }
    }
    response = client.post("/api/v1/categorization/feedback", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert sorted(data["updated_categories"]) == ["Dining", "Taxi & Rideshare"]


def test_feedback_empty_corrections(client):
    response = client.post("/api/v1/categorization/feedback", json={"corrections": {}})
    assert response.status_code == 400


# ── /models ───────────────────────────────────────────────────────────────────


def test_models_endpoint(client):
    response = client.get("/api/v1/categorization/models")

    assert response.status_code == 200
    data = response.json()
    assert data["base_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert data["embedding_dim"] == 384
    assert data["classifier_type"] == "cosine_similarity_zero_shot"
    assert data["adapter_type"] == "linear_adapter"
    assert data["confidence_threshold"] == 0.75
