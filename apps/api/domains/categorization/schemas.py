"""Pydantic schemas for the categorization domain.

Fixes IMP-04: all endpoints use typed models instead of raw dicts.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ClassifyRequest(BaseModel):
    """Request to classify a single transaction."""

    description: str = Field(..., max_length=1000)


class ClassifyResponse(BaseModel):
    """Classification result for a single transaction."""

    category: str
    confidence: float
    model_used: str = "minilm-cosine-v2"


class BatchClassifyRequest(BaseModel):
    """Request to classify multiple transactions in batch."""

    descriptions: list[str] = Field(..., max_length=1000, description="List of transaction descriptions to classify")


class BatchClassifyResponse(BaseModel):
    """Batch classification result."""

    predictions: list[ClassifyResponse]


class FeedbackRequest(BaseModel):
    """User corrections for active learning."""

    corrections: dict[str, str | list[str]] = Field(
        ...,
        description="Map of description→category or category→[descriptions]",
    )
