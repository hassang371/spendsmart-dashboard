"""Tests for classification router."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from apps.api.main import app

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
    """Tests for /classify endpoint."""
    
    def test_classify_no_auth(self):
        """Test classification without authentication."""
        response = client.post("/api/v1/classify", json={
            "description": "Test transaction",
            "use_latest_model": True,
        })
        assert response.status_code == 401
    
    @patch("apps.api.routers.classify.classify_transaction_task")
    @patch("apps.api.deps.get_user_client")
    def test_classify_success(self, mock_get_client, mock_task, mock_user_client):
        """Test successful classification."""
        mock_get_client.return_value = mock_user_client
        mock_task.delay.return_value.get.return_value = {
            "category": "Food & Dining",
            "confidence": 0.95,
        }
        
        with patch("os.path.exists", return_value=True):
            response = client.post("/api/v1/classify", json={
                "description": "Starbucks coffee",
                "use_latest_model": True,
            })
        
        assert response.status_code == 200
        data = response.json()
        assert data["category"] == "Food & Dining"
        assert data["confidence"] == 0.95
