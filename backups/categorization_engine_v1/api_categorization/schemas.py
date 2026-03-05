"""Pydantic schemas for the categorization domain.

Fixes IMP-04: all endpoints use typed models instead of raw dicts.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ClassifyRequest(BaseModel):
    """Request to classify a single transaction."""

    description: str = Field(..., max_length=1000)
    use_latest_model: bool = True
    model_path: Optional[str] = Field(default=None, max_length=255)


class ClassifyResponse(BaseModel):
    """Classification result for a single transaction."""

    category: str
    confidence: float
    model_used: str = "hypcd"


class BatchClassifyRequest(BaseModel):
    """Request to classify multiple transactions in batch."""

    descriptions: list[str] = Field(..., max_length=1000, description="List of transaction descriptions to classify")
    use_latest_model: bool = True


class BatchClassifyResponse(BaseModel):
    """Batch classification result."""

    predictions: list[ClassifyResponse]


class FeedbackRequest(BaseModel):
    """User corrections for active learning."""

    corrections: dict[str, str | list[str]] = Field(
        ...,
        description="Map of description→category or category→[descriptions]",
    )


class DiscoverRequest(BaseModel):
    """Request for Generalized Category Discovery."""

    descriptions: list[str] = Field(..., max_length=10000, description="List of transaction descriptions")
    n_clusters: int = Field(default=5, ge=1, le=50)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
