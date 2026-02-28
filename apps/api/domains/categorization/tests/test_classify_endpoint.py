"""Tests for POST /classify and POST /feedback endpoints."""
import pytest
from httpx import AsyncClient, ASGITransport
from types import SimpleNamespace

from apps.api.main import app
from apps.api.core.auth import get_user_client
import torch


@pytest.fixture
def mock_classifier(monkeypatch):
    """Mock HypCDClassifier to avoid loading the full model."""

    class MockClassifier:
        def __init__(self):
            self.updated_anchors = {}  # Track feedback calls

        def predict_batch(self, texts):
            results = []
            for text in texts:
                upper = text.upper()
                if "UBER" in upper:
                    results.append(("Transport", 0.9, torch.zeros(1, 384)))
                elif "ZOMATO" in upper or "SWIGGY" in upper:
                    results.append(("Food", 0.85, torch.zeros(1, 384)))
                elif "NETFLIX" in upper:
                    results.append(("Entertainment", 0.8, torch.zeros(1, 384)))
                else:
                    results.append(("Misc", 0.5, torch.zeros(1, 384)))
            return results

        def update_anchors(self, labeled_texts):
            self.updated_anchors.update(labeled_texts)

    mock_instance = MockClassifier()
    monkeypatch.setattr(
        "apps.api.domains.categorization.service.get_classifier", lambda: mock_instance
    )
    return mock_instance


@pytest.fixture(autouse=True)
def mock_user_client():
    class MockTable:
        def insert(self, _rows):
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    class MockClient:
        def __init__(self):
            self.auth = SimpleNamespace(
                get_user=lambda: SimpleNamespace(
                    user=SimpleNamespace(id="test-user-id")
                )
            )

        def table(self, _name):
            return MockTable()

    app.dependency_overrides[get_user_client] = lambda: MockClient()
    yield
    app.dependency_overrides.clear()


# ─── /classify tests ───


@pytest.mark.asyncio
async def test_classify_returns_category_map(mock_classifier):
    """POST /classify with unique descriptions returns {description: category} map."""
    payload = {
        "descriptions": ["Uber trip to airport", "Zomato order #123", "Random store"]
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/v1/categorization/classify/batch", json=payload)

    assert response.status_code == 200
    data = response.json()

    # The new structure returns BatchClassifyResponse with predictions list
    assert "predictions" in data
    assert len(data["predictions"]) == 3
    preds = data["predictions"]
    
    assert preds[0]["category"] == "Transport"
    assert preds[1]["category"] == "Food"
    assert preds[2]["category"] == "Misc"


@pytest.mark.asyncio
async def test_classify_empty_descriptions(mock_classifier):
    """POST /classify with empty list returns 400."""
    payload = {"descriptions": []}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/v1/categorization/classify/batch", json=payload)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_classify_missing_descriptions_field(mock_classifier):
    """POST /classify without descriptions field returns 400."""
    payload = {"texts": ["something"]}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/v1/categorization/classify/batch", json=payload)

    assert response.status_code == 422


# ─── /feedback tests ───


@pytest.mark.asyncio
async def test_feedback_updates_classifier(mock_classifier):
    """POST /feedback accepts category correction payload."""
    payload = {
        "corrections": {"Food": ["Uber Eats delivery"], "Transport": ["Ola cab ride"]}
    }

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/v1/categorization/feedback", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"

    assert sorted(data["updated_categories"]) == ["Food", "Transport"]


@pytest.mark.asyncio
async def test_feedback_empty_corrections(mock_classifier):
    """POST /feedback with empty corrections returns 400."""
    payload = {"corrections": {}}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/v1/categorization/feedback", json=payload)

    assert response.status_code == 400
