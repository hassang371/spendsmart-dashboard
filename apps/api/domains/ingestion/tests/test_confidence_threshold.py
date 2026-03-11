"""Tests for _classify_descriptions confidence handling in the v2 ingestion pipeline."""

from unittest.mock import patch


def test_classify_descriptions_returns_confidence():
    """_classify_descriptions must return confidence alongside category."""
    mock_clf = [
        {"category": "Food", "confidence": 0.95},
        {"category": "Taxi & Rideshare", "confidence": 0.60},
    ]
    with patch(
        "apps.api.domains.categorization.service.classify_batch_in_process",
        return_value=mock_clf,
    ):
        from apps.api.domains.ingestion import router as ingestion_router

        result = ingestion_router._classify_descriptions(["swiggy", "some unknown"])

    assert result["swiggy"]["category"] == "Food"
    assert result["swiggy"]["confidence"] == 0.95
    assert result["some unknown"]["category"] == "Taxi & Rideshare"
    assert result["some unknown"]["confidence"] == 0.60


def test_classify_descriptions_fallback_uses_keyword_matcher():
    """When classifier is unavailable, KeywordMatcher is used as fallback."""
    with patch(
        "apps.api.domains.categorization.service.classify_batch_in_process",
        side_effect=RuntimeError("classifier offline"),
    ):
        from apps.api.domains.ingestion import router as ingestion_router

        result = ingestion_router._classify_descriptions(["swiggy order", "xyz unknown thing"])

    assert isinstance(result["swiggy order"], dict)
    assert "category" in result["swiggy order"]
    assert "confidence" in result["swiggy order"]
    assert result["swiggy order"]["category"] == "Food"
    assert result["swiggy order"]["confidence"] == 1.0
    assert result["xyz unknown thing"]["category"] == "Uncategorized"
    assert result["xyz unknown thing"]["confidence"] == 0.0
