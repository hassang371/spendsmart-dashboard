"""Tests for categorization domain.

Verifies BUG-03 fix (single classify endpoint) and BUG-04 fix
(in-process batch classification without Celery).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.api.domains.categorization.router import router
from apps.api.core.auth import get_user_client


@pytest.fixture
def app():
    """Create a test app with the categorization router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


@pytest.fixture
def mock_user_client():
    """Mock authenticated user client."""
    mock_client = Mock()
    mock_user = Mock()
    mock_user.id = "test-user-123"
    mock_user.email = "test@example.com"
    mock_client.auth.get_user.return_value = Mock(user=mock_user)
    return mock_client


@pytest.fixture
def client(app, mock_user_client):
    app.dependency_overrides[get_user_client] = lambda: mock_user_client
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def mock_classifier():
    """Mock HypCD classifier to avoid loading model during tests."""
    mock = MagicMock()
    mock.predict_batch.return_value = [
        ("Food & Dining", 0.95, None),
        ("Transport", 0.87, None),
    ]

    with patch("apps.api.domains.categorization.service._classifier", mock):
        with patch("apps.api.domains.categorization.service._classifier_lock"):
            yield mock


class TestClassifyEndpoint:
    """BUG-03 fix: Single /classify endpoint."""

    def test_classify_single_returns_200(self, client):
        response = client.post("/api/v1/categorization/classify", json={
            "description": "Starbucks coffee",
        })
        assert response.status_code == 200
        data = response.json()
        assert "category" in data
        assert "confidence" in data
        assert "model_used" in data

    def test_classify_no_auth(self, app):
        """Without auth, should return 401."""
        app.dependency_overrides.clear()
        c = TestClient(app)
        response = c.post("/api/v1/categorization/classify", json={
            "description": "test",
        })
        assert response.status_code == 401


class TestBatchClassify:
    """BUG-04 fix: In-process batch classification."""

    def test_batch_classify_returns_predictions(self, client, mock_classifier):
        """Batch classify should return results for all descriptions."""
        response = client.post("/api/v1/categorization/classify/batch", json={
            "descriptions": ["Starbucks coffee", "Uber ride"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert len(data["predictions"]) == 2
        assert data["predictions"][0]["category"] == "Food & Dining"

    def test_batch_classify_calls_predict_batch_once(self, client, mock_classifier):
        """BUG-04: Should call predict_batch ONCE, not N separate times."""
        client.post("/api/v1/categorization/classify/batch", json={
            "descriptions": ["A", "B", "C"],
        })
        # predict_batch should be called exactly once with all descriptions
        mock_classifier.predict_batch.assert_called_once()

    def test_batch_classify_empty_descriptions(self, client):
        """Empty descriptions list should return 400."""
        response = client.post("/api/v1/categorization/classify/batch", json={
            "descriptions": [],
        })
        assert response.status_code == 400


class TestFeedback:
    """Tests for feedback/active learning endpoint."""

    def test_feedback_empty_corrections(self, client):
        response = client.post("/api/v1/categorization/feedback", json={
            "corrections": {},
        })
        assert response.status_code == 400
