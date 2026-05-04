"""Inference module tests (post-Stage 5).

The legacy ``_MODEL_CACHE`` / ``load_model`` / ``invalidate_cache``
shims were deleted in Stage 5 (BUG-018) — see
``test_inference_module_exports_bounded_cache_not_raw_dict.py`` for the
regression guard. What remains here is the surface that ``predict_with_tft``
and ``get_latest_checkpoint_path`` actually need.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import torch

from packages.forecasting.inference import get_latest_checkpoint_path, predict_with_tft


def test_get_latest_checkpoint_path():
    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"checkpoint_path": "checkpoints/u1/job1/tft.ckpt"}
    ]

    path = get_latest_checkpoint_path(mock_supabase, "u1")
    assert path == "checkpoints/u1/job1/tft.ckpt"

    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []
    path = get_latest_checkpoint_path(mock_supabase, "u1")
    assert path is None


def test_predict_with_tft():
    mock_model = MagicMock()
    mock_model.loss.quantiles = [0.1, 0.5, 0.9]

    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    df = pd.DataFrame(
        {
            "date": dates,
            "amount": np.random.uniform(-100, 100, 100),
            "description": ["foo"] * 100,
        }
    )
    df.loc[df.index % 30 == 0, "amount"] = 5000

    horizon = 30
    fake_preds = torch.tensor([[[10.0, 50.0, 90.0]] * horizon])
    mock_model.predict.return_value = fake_preds
    mock_model.dataset_parameters = {
        "max_encoder_length": 60,
        "max_prediction_length": 30,
    }

    mock_reference_ds = MagicMock()
    mock_pred_ds = MagicMock()
    mock_pred_ds.to_dataloader.return_value = MagicMock()

    with (
        patch(
            "packages.forecasting.inference.create_timeseries_dataset",
            return_value=mock_reference_ds,
        ) as mock_create_ds,
        patch("packages.forecasting.inference.TimeSeriesDataSet") as mock_ts_cls,
    ):
        mock_ts_cls.from_dataset.return_value = mock_pred_ds

        result = predict_with_tft(mock_model, df, horizon=horizon)

        mock_create_ds.assert_called_once()

        # BUG-004: from_dataset must receive a TimeSeriesDataSet INSTANCE,
        # not a dict.
        call_args = mock_ts_cls.from_dataset.call_args
        first_arg = call_args[0][0]
        assert first_arg is mock_reference_ds

        assert "forecast" in result
        forecast = result["forecast"]
        assert len(forecast) == horizon
        # BUG-031: predict_with_tft now anchors day-0 P50 to the user's
        # last observed closing_balance and shifts every quantile by the
        # same delta. Assert the SPREAD (which is shift-invariant) rather
        # than absolute levels.
        p10, p50, p90 = forecast[0]["p10"], forecast[0]["p50"], forecast[0]["p90"]
        assert p50 - p10 == pytest.approx(40.0, abs=0.01)
        assert p90 - p50 == pytest.approx(40.0, abs=0.01)


def test_predict_with_tft_dataset_construction_failure():
    mock_model = MagicMock()
    mock_model.loss.quantiles = [0.1, 0.5, 0.9]
    mock_model.dataset_parameters = {}

    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    df = pd.DataFrame({"date": dates, "amount": np.random.uniform(-100, 100, 100)})

    with patch(
        "packages.forecasting.inference.create_timeseries_dataset",
        side_effect=ValueError("schema mismatch"),
    ):
        result = predict_with_tft(mock_model, df, horizon=7)

    assert "error" in result
    assert "Inference dataset construction failed" in result["error"]
