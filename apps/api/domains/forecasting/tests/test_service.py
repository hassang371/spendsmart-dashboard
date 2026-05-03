"""Stage 1 stub-tests for ForecastService.

Stage 1 ships a minimal ForecastService skeleton — basic tier routing
plus a predict() method whose response shape mirrors the legacy CSV
upload contract (``predictions`` list, ``horizon_days``, ``model``,
``note``). Stage 5 swaps the response shape to RFC-003's
``ForecastResponse`` and adds insights + prediction logging.

These tests pin the Stage 1 contract so Stage 5's expansion has a
clear baseline to refactor against.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd
import pytest

from apps.api.domains.forecasting.service import ForecastService


def _make_daily_transactions(n_days: int = 50) -> pd.DataFrame:
    """Synthetic raw-transactions DataFrame (date + amount columns)."""
    rows = []
    start = pd.Timestamp("2026-01-01")
    for i in range(n_days):
        rows.append({"date": start + pd.Timedelta(days=i), "amount": -10.0 - i})
    return pd.DataFrame(rows)


def test_forecast_service_predict_returns_legacy_shape():
    """Stage 1 stub: response carries ``predictions`` + ``horizon_days``."""
    service = ForecastService(client=MagicMock())
    df = _make_daily_transactions()

    result = service.predict(df, user_id="user-stage1", horizon=7)

    assert "predictions" in result
    assert "horizon_days" in result
    assert result["horizon_days"] == 7
    assert isinstance(result["predictions"], list)
    assert len(result["predictions"]) == 7


def test_forecast_service_predict_each_point_has_basic_keys():
    """Each prediction point must include the legacy spend / income / net keys."""
    service = ForecastService(client=MagicMock())
    df = _make_daily_transactions()

    result = service.predict(df, user_id="user-stage1", horizon=7)

    for point in result["predictions"]:
        assert "day_offset" in point
        assert "predicted_spend" in point
        assert "predicted_income" in point
        assert "predicted_net" in point


def test_forecast_service_predict_rejects_empty_dataframe():
    """An empty DataFrame should raise ValueError (router maps to 400)."""
    service = ForecastService(client=MagicMock())
    df = pd.DataFrame(columns=["date", "amount"])

    with pytest.raises(ValueError):
        service.predict(df, user_id="user-stage1", horizon=7)
