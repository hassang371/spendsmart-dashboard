import pytest
from httpx import AsyncClient, ASGITransport
from types import SimpleNamespace

from apps.api.main import app
from apps.api.deps import get_user_client
import io
import torch


@pytest.fixture
def mock_classifier(monkeypatch):
    """
    Mock the HypCDClassifier to avoid loading the full model during API tests.
    """

    class MockClassifier:
        def predict_batch(self, texts):
            # Return dummy predictions
            results = []
            for text in texts:
                if "UBER" in text.upper():
                    results.append(("Transport", 0.9, torch.zeros(1, 384)))
                elif "BURGER" in text.upper():
                    results.append(("Food", 0.8, torch.zeros(1, 384)))
                else:
                    results.append(("General", 0.5, torch.zeros(1, 384)))
            return results

    # Patch the get_classifier function in ingestion.py
    # We need to patch where it's imported or used.
    # Since we use `get_classifier` in `apps.api.routers.ingestion`, we patch that.

    # We need to mock the `HypCDClassifier` class itself or the `get_classifier` function.
    # Let's patch `apps.api.routers.ingestion.get_classifier` to return our mock.

    mock_instance = MockClassifier()
    monkeypatch.setattr(
        "apps.api.routers.ingestion.get_classifier", lambda: mock_instance
    )
    return mock_instance


@pytest.fixture(autouse=True)
def mock_user_client():
    class MockClient:
        def __init__(self):
            self.auth = SimpleNamespace(
                get_user=lambda: SimpleNamespace(
                    user=SimpleNamespace(id="test-user-id")
                )
            )

    app.dependency_overrides[get_user_client] = lambda: MockClient()
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ingest_csv_categorization(mock_classifier):
    """
    Test that CSV ingestion calls the classifier and adds categories.
    """
    csv_content = "date,amount,merchant\n2023-10-27,15.50,UBER *TRIP\n2023-10-28,12.00,BURGER KING\n2023-10-29,50.00,Unknown Store"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        response = await ac.post("/api/v1/ingest/csv", files=files)

    assert response.status_code == 200
    data = response.json()

    assert data["count"] == 3
    transactions = data["transactions"]

    # Check categorization
    assert transactions[0]["merchant"] in ("UBER *TRIP", "Uber")
    assert transactions[0]["category"] == "Transport"

    assert transactions[1]["merchant"] in ("BURGER KING", "Burger King")
    assert transactions[1]["category"] == "Food"

    assert transactions[2]["merchant"] == "Unknown Store"
    assert transactions[2]["category"] == "General"
