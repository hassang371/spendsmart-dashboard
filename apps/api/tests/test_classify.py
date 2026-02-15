"""Tests for classification router."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from apps.api.main import app
from apps.api.routers.classify import get_user_client

client = TestClient(app)


@pytest.fixture
def mock_user_client():
    """Mock authenticated user client."""
    mock_client = Mock()
    mock_user = Mock()
    mock_user.id = "test-user-123"
    mock_client.auth.get_user.return_value = Mock(user=mock_user)
    return mock_client


class TestClassifyEndpoint:
    """Tests for /classify/batch endpoint."""

    @pytest.fixture(autouse=True)
    def override_user_client(self, mock_user_client):
        app.dependency_overrides[get_user_client] = lambda: mock_user_client
        yield
        app.dependency_overrides.pop(get_user_client, None)
    
    def test_classify_no_auth(self):
        """Test classification without authentication."""
        app.dependency_overrides.pop(get_user_client, None)
        response = client.post("/api/v1/classify/batch", json={
            "descriptions": ["Test transaction"],
            "use_latest_model": True,
        })
        assert response.status_code == 401
    
    @patch("apps.api.routers.classify.classify_transaction_task")
    def test_classify_success(self, mock_task, mock_user_client):
        """Test successful classification."""
        mock_task.delay.return_value.get.return_value = {
            "category": "Food & Dining",
            "confidence": 0.95,
        }

        with patch("apps.api.routers.classify.os.path.exists", return_value=True):
            response = client.post("/api/v1/classify/batch", json={
                "descriptions": ["Starbucks coffee"],
                "use_latest_model": True,
            })

        assert response.status_code == 200
        data = response.json()
        assert "predictions" in data
        assert len(data["predictions"]) == 1
        assert data["predictions"][0]["category"] == "Food & Dining"
        assert data["predictions"][0]["confidence"] == 0.95
