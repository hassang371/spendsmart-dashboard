"""Integration tests for the categorization API endpoints (v2).

Tests the /classify/batch, /classify, /feedback, /metrics, and /models endpoints
using the v2 TransactionClassifier (MiniLM + Cosine Similarity).
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.domains.categorization.router import router
from apps.api.core.auth import CurrentUser, get_current_user, get_current_user_id, get_user_client


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_user_client():
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_client.auth.get_user.return_value = MagicMock(user=mock_user)

    # Mock table calls for feedback insert
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.select.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.execute.return_value = MagicMock(data=[])

    return mock_client


@pytest.fixture
def client(app, mock_user_client):
    app.dependency_overrides[get_user_client] = lambda: mock_user_client
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-id", email=None)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_classify(monkeypatch):
    """Mock the classify functions to avoid loading MiniLM model during tests."""

    def _mock_classify_batch(texts):
        results = []
        for text in texts:
            upper = text.upper()
            if "UBER" in upper:
                results.append({"category": "Taxi & Rideshare", "confidence": 0.9})
            elif "ZOMATO" in upper or "SWIGGY" in upper:
                results.append({"category": "Dining", "confidence": 0.95})
            elif "NETFLIX" in upper:
                results.append({"category": "Subscriptions", "confidence": 0.88})
            elif "AIRBNB" in upper:
                results.append({"category": "Hotels & Stays", "confidence": 0.92})
            else:
                results.append({"category": "Uncategorized", "confidence": 0.3})
        return results

    def _mock_classify_single(text):
        return _mock_classify_batch([text])[0]

    class _MockClassifier:
        confidence_threshold = 0.75

    monkeypatch.setattr(
        "apps.api.domains.categorization.router.classify_batch_in_process",
        _mock_classify_batch,
    )
    monkeypatch.setattr(
        "apps.api.domains.categorization.router.classify_single",
        _mock_classify_single,
    )
    monkeypatch.setattr(
        "apps.api.domains.categorization.router.get_classifier",
        lambda: _MockClassifier(),
    )


# ─── /classify/batch tests ───


def test_batch_classify_returns_predictions(client):
    """POST /classify/batch returns predictions list with v2 categories."""
    payload = {
        "descriptions": ["Uber trip to airport", "Swiggy food order", "Random unknown store"]
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
    """POST /classify/batch with empty list returns 400."""
    response = client.post("/api/v1/categorization/classify/batch", json={"descriptions": []})
    assert response.status_code == 400


def test_batch_classify_missing_field(client):
    """POST /classify/batch without descriptions field returns 422."""
    response = client.post("/api/v1/categorization/classify/batch", json={"texts": ["something"]})
    assert response.status_code == 422


# ─── /classify (single) tests ───


def test_single_classify_food(client):
    """POST /classify returns correct category for known food merchant."""
    response = client.post(
        "/api/v1/categorization/classify",
        json={"description": "Swiggy food order"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Dining"
    assert data["model_used"] == "minilm-cosine-v2"


def test_single_classify_unknown(client):
    """POST /classify returns Uncategorized for unknown description."""
    response = client.post(
        "/api/v1/categorization/classify",
        json={"description": "Random store purchase"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "Uncategorized"


# ─── /feedback tests ───


def test_feedback_accepts_corrections(client):
    """POST /feedback accepts category correction payload."""
    payload = {
        "corrections": {"Dining": ["Uber Eats delivery"], "Taxi & Rideshare": ["Ola cab ride"]}
    }
    response = client.post("/api/v1/categorization/feedback", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert sorted(data["updated_categories"]) == ["Dining", "Taxi & Rideshare"]


def test_feedback_empty_corrections(client):
    """POST /feedback with empty corrections returns 400."""
    response = client.post("/api/v1/categorization/feedback", json={"corrections": {}})
    assert response.status_code == 400


# ─── /models tests ───


def test_models_endpoint(client):
    """GET /models returns v2 model info."""
    response = client.get("/api/v1/categorization/models")

    assert response.status_code == 200
    data = response.json()
    assert data["base_model"] == "sentence-transformers/all-MiniLM-L6-v2"
    assert data["embedding_dim"] == 384
    assert data["classifier_type"] == "cosine_similarity_zero_shot"
    assert data["adapter_type"] == "linear_adapter"
    assert data["confidence_threshold"] == 0.75
