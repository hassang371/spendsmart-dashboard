"""Tests for the Chronos-2 zero-shot engine.

Override per RFC-003 §1 "Chronos-path quantile expansion": the engine
emits all seven RFC-003 quantiles per forecast point — p2, p10, p25,
p50, p75, p90, p98 — not the historical 3-quantile shape.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import torch

QUANTILE_KEYS = ("p2", "p10", "p25", "p50", "p75", "p90", "p98")


def _make_daily_df(n_days: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    return pd.DataFrame(
        {
            "date": dates,
            "daily_spend": rng.uniform(10, 100, n_days),
            "daily_income": rng.uniform(0, 200, n_days),
            "closing_balance": np.cumsum(rng.uniform(-20, 30, n_days)),
        }
    )


def test_predict_returns_correct_shape():
    """Predict returns a forecast list of length=horizon, plus metadata."""
    from packages.forecasting.chronos_engine import ChronosEngine

    with patch("packages.forecasting.chronos_engine.BaseChronosPipeline") as MockPipeline:
        mock_instance = MagicMock(spec=["predict_quantiles"])
        mock_instance.predict_quantiles.return_value = (
            torch.randn(1, 30, 7).abs(),
            torch.randn(1, 30).abs(),
        )
        MockPipeline.from_pretrained.return_value = mock_instance

        engine = ChronosEngine(model_name="mock-model")
        result = engine.predict(_make_daily_df(), horizon=30)

    assert "forecast" in result
    assert len(result["forecast"]) == 30
    assert result["model_type"] == "chronos2"
    assert result["horizon"] == 30
    assert result["model_version"] == "mock-model"


def test_predict_emits_all_seven_quantiles():
    """Each forecast point must carry all RFC-003 quantile keys."""
    from packages.forecasting.chronos_engine import ChronosEngine

    with patch("packages.forecasting.chronos_engine.BaseChronosPipeline") as MockPipeline:
        mock_instance = MagicMock(spec=["predict_quantiles"])
        mock_instance.predict_quantiles.return_value = (
            torch.randn(1, 30, 7).abs(),
            torch.randn(1, 30).abs(),
        )
        MockPipeline.from_pretrained.return_value = mock_instance

        engine = ChronosEngine(model_name="mock-model")
        result = engine.predict(_make_daily_df(), horizon=30)

    for point in result["forecast"]:
        for key in QUANTILE_KEYS:
            assert key in point, f"missing quantile {key} in {point}"


def test_predict_quantile_ordering():
    """p2 <= p10 <= p25 <= p50 <= p75 <= p90 <= p98 for every point."""
    from packages.forecasting.chronos_engine import ChronosEngine

    with patch("packages.forecasting.chronos_engine.BaseChronosPipeline") as MockPipeline:
        # Sort along quantile axis so the per-day quantile vector is monotonic.
        sorted_q = torch.sort(torch.randn(1, 30, 7).abs(), dim=2).values
        mock_instance = MagicMock(spec=["predict_quantiles"])
        mock_instance.predict_quantiles.return_value = (sorted_q, sorted_q[:, :, 3])
        MockPipeline.from_pretrained.return_value = mock_instance

        engine = ChronosEngine(model_name="mock-model")
        result = engine.predict(_make_daily_df(), horizon=30)

    for point in result["forecast"]:
        values = [point[k] for k in QUANTILE_KEYS]
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1] + 1e-6, f"quantiles out of order at {point['date']}: {values}"


def test_predict_empty_df_raises():
    """Empty DataFrame should raise a clear ValueError."""
    from packages.forecasting.chronos_engine import ChronosEngine

    with patch("packages.forecasting.chronos_engine.ChronosPipeline") as MockPipeline:
        MockPipeline.from_pretrained.return_value = MagicMock()
        engine = ChronosEngine(model_name="mock-model")

        with pytest.raises(ValueError, match="No transaction data"):
            engine.predict(pd.DataFrame(), horizon=30)
