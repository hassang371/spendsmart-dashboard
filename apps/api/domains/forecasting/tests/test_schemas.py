"""Schema-contract tests for the RFC-003 §1 forecast API models.

These tests pin the v1 forecast contract so Stage 5 (service wiring) and
later UI / harness stages can build against a frozen shape. The tests
exercise the validators that Pydantic generates from the model's type
hints (Literal narrowing, Field(min_length/max_length/ge/le), and the
seven required quantile fields on ``ForecastPoint``).

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §1
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from apps.api.domains.forecasting.schemas import (
    ForecastInsights,
    ForecastPoint,
    ForecastResponse,
    LowestBalance,
    QuantileSnapshot,
    TrainStatusResponse,
    VariableImportance,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _valid_point(date: str = "2026-05-01") -> dict:
    """Return a dict that ForecastPoint will accept."""
    return {
        "date": date,
        "p2": 100.0,
        "p10": 110.0,
        "p25": 120.0,
        "p50": 130.0,
        "p75": 140.0,
        "p90": 150.0,
        "p98": 160.0,
    }


def _valid_insights() -> ForecastInsights:
    return ForecastInsights(
        lowest_balance=LowestBalance(date="2026-05-15", p10=50.0, p50=80.0),
        month_end=QuantileSnapshot(p10=200.0, p50=300.0, p90=400.0),
        predicted_monthly_spend=-1500.0,
        predicted_monthly_income=2000.0,
        confidence_band_width=120.5,
        primary_drivers=[VariableImportance(feature="day_of_week", weight=0.42)],
        safe_to_spend=250.0,
        overdraft_risk_score=0.0,
        floor_used=0.0,
        floor_source="auto_p10_history",
    )


def _valid_response_kwargs(forecast_len: int = 1) -> dict:
    return {
        "forecast": [_valid_point() for _ in range(forecast_len)],
        "model_type": "tft_hybrid",
        "model_version": "v0.1.0",
        "horizon": forecast_len,
        "confidence": "medium",
        "variable_importance": None,
        "insights": _valid_insights(),
        "prediction_id": uuid4(),
    }


# ---------------------------------------------------------------------------
# ForecastPoint
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing",
    ["p2", "p10", "p25", "p50", "p75", "p90", "p98"],
)
def test_forecast_point_requires_all_seven_quantiles(missing: str) -> None:
    """Dropping any of the 7 quantiles must raise ValidationError."""
    payload = _valid_point()
    payload.pop(missing)
    with pytest.raises(ValidationError):
        ForecastPoint(**payload)


# ---------------------------------------------------------------------------
# ForecastResponse — horizon
# ---------------------------------------------------------------------------


def test_forecast_response_horizon_lower_bound() -> None:
    """horizon=0 must be rejected (Field(ge=1))."""
    kwargs = _valid_response_kwargs(forecast_len=1)
    kwargs["horizon"] = 0
    with pytest.raises(ValidationError):
        ForecastResponse(**kwargs)


def test_forecast_response_horizon_upper_bound() -> None:
    """horizon=31 rejected; horizon=30 accepted."""
    kwargs_31 = _valid_response_kwargs(forecast_len=30)
    kwargs_31["horizon"] = 31
    with pytest.raises(ValidationError):
        ForecastResponse(**kwargs_31)

    kwargs_30 = _valid_response_kwargs(forecast_len=30)
    kwargs_30["horizon"] = 30
    resp = ForecastResponse(**kwargs_30)
    assert resp.horizon == 30


# ---------------------------------------------------------------------------
# ForecastResponse — required fields
# ---------------------------------------------------------------------------


def test_forecast_response_requires_insights() -> None:
    """Omitting `insights` must raise ValidationError."""
    kwargs = _valid_response_kwargs()
    kwargs.pop("insights")
    with pytest.raises(ValidationError):
        ForecastResponse(**kwargs)


def test_forecast_response_prediction_id_is_uuid() -> None:
    """Valid UUID strings are coerced; non-uuid strings rejected."""
    kwargs = _valid_response_kwargs()
    kwargs["prediction_id"] = "550e8400-e29b-41d4-a716-446655440000"
    resp = ForecastResponse(**kwargs)
    assert isinstance(resp.prediction_id, UUID)
    assert str(resp.prediction_id) == "550e8400-e29b-41d4-a716-446655440000"

    kwargs["prediction_id"] = "not-a-uuid"
    with pytest.raises(ValidationError):
        ForecastResponse(**kwargs)


# ---------------------------------------------------------------------------
# ForecastResponse — forecast list bounds
# ---------------------------------------------------------------------------


def test_forecast_response_forecast_min_length() -> None:
    """An empty forecast list must be rejected (min_length=1)."""
    kwargs = _valid_response_kwargs(forecast_len=1)
    kwargs["forecast"] = []
    with pytest.raises(ValidationError):
        ForecastResponse(**kwargs)


def test_forecast_response_forecast_max_length() -> None:
    """A forecast list of 31 entries must be rejected (max_length=30)."""
    kwargs = _valid_response_kwargs(forecast_len=30)
    kwargs["forecast"] = [_valid_point() for _ in range(31)]
    kwargs["horizon"] = 30  # keep horizon valid; the failing field is forecast
    with pytest.raises(ValidationError):
        ForecastResponse(**kwargs)


# ---------------------------------------------------------------------------
# ForecastResponse — Literal narrowing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model_type", ["chronos2", "tft_hybrid", "ensemble"])
def test_forecast_response_model_type_literal_accepts(model_type: str) -> None:
    """All three Literal model_type values must be accepted."""
    kwargs = _valid_response_kwargs()
    kwargs["model_type"] = model_type
    resp = ForecastResponse(**kwargs)
    assert resp.model_type == model_type


def test_forecast_response_model_type_literal_rejects() -> None:
    """Anything outside the Literal set must be rejected."""
    kwargs = _valid_response_kwargs()
    kwargs["model_type"] = "weird_model"
    with pytest.raises(ValidationError):
        ForecastResponse(**kwargs)


# ---------------------------------------------------------------------------
# ForecastInsights — floor_source Literal
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", ["auto_p10_history", "user_override"])
def test_forecast_insights_floor_source_literal_accepts(source: str) -> None:
    insights = ForecastInsights(
        lowest_balance=LowestBalance(date="2026-05-15", p10=0.0, p50=0.0),
        month_end=QuantileSnapshot(p10=0.0, p50=0.0, p90=0.0),
        predicted_monthly_spend=0.0,
        predicted_monthly_income=0.0,
        confidence_band_width=0.0,
        primary_drivers=[],
        safe_to_spend=0.0,
        overdraft_risk_score=0.0,
        floor_used=0.0,
        floor_source=source,
    )
    assert insights.floor_source == source


def test_forecast_insights_floor_source_literal_rejects() -> None:
    with pytest.raises(ValidationError):
        ForecastInsights(
            lowest_balance=LowestBalance(date="2026-05-15", p10=0.0, p50=0.0),
            month_end=QuantileSnapshot(p10=0.0, p50=0.0, p90=0.0),
            predicted_monthly_spend=0.0,
            predicted_monthly_income=0.0,
            confidence_band_width=0.0,
            primary_drivers=[],
            safe_to_spend=0.0,
            overdraft_risk_score=0.0,
            floor_used=0.0,
            floor_source="something_else",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# TrainStatusResponse
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["no_model", "pending", "claimed", "processing", "completed", "failed"],
)
def test_train_status_response_accepts_each_literal(status: str) -> None:
    resp = TrainStatusResponse(status=status)
    assert resp.status == status


def test_train_status_response_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        TrainStatusResponse(status="weird")  # type: ignore[arg-type]
