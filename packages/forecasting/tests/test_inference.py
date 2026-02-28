import pytest
import pandas as pd
import numpy as np
import torch
from unittest.mock import MagicMock, patch
from packages.forecasting.inference import (
    get_latest_checkpoint_path,
    load_model,
    predict_with_tft,
    invalidate_cache,
    _MODEL_CACHE,
)


@pytest.fixture
def mock_supabase():
    return MagicMock()


def test_get_latest_checkpoint_path(mock_supabase):
    # Setup mock response
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"checkpoint_path": "checkpoints/u1/job1/tft.ckpt"}
    ]

    path = get_latest_checkpoint_path(mock_supabase, "u1")
    assert path == "checkpoints/u1/job1/tft.ckpt"

    # Test empty
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = (
        []
    )
    path = get_latest_checkpoint_path(mock_supabase, "u1")
    assert path is None


@patch("packages.forecasting.inference.TemporalFusionTransformer")
def test_load_model(mock_tft_cls, mock_supabase):
    user_id = "u1"

    # Mock get_latest_checkpoint_path
    with patch(
        "packages.forecasting.inference.get_latest_checkpoint_path"
    ) as mock_get_path:
        mock_get_path.return_value = "path/to/ckpt"

        # Mock storage download
        mock_supabase.storage.from_.return_value.download.return_value = (
            b"fake-model-bytes"
        )

        # Mock load_from_checkpoint
        mock_model = MagicMock()
        mock_tft_cls.load_from_checkpoint.return_value = mock_model

        # Test loading logic
        invalidate_cache(user_id)
        model = load_model(mock_supabase, user_id)

        assert model is mock_model
        assert user_id in _MODEL_CACHE
        mock_supabase.storage.from_.return_value.download.assert_called_once()

        # Test caching
        mock_supabase.storage.from_.return_value.download.reset_mock()
        model2 = load_model(mock_supabase, user_id)
        assert model2 is model
        mock_supabase.storage.from_.return_value.download.assert_not_called()


def test_predict_with_tft():
    # Mock model
    mock_model = MagicMock()
    # Mock quantiles
    mock_model.loss.quantiles = [0.1, 0.5, 0.9]

    # Create fake history
    dates = pd.date_range("2025-01-01", periods=100, freq="D")
    df = pd.DataFrame(
        {
            "date": dates,
            "amount": np.random.uniform(-100, 100, 100),
            "description": ["foo"] * 100,
        }
    )
    # Add income periodically for payday detection
    df.loc[df.index % 30 == 0, "amount"] = 5000

    # Mock predict output
    # shape: (1, 30, 3) for 3 quantiles
    horizon = 30
    fake_preds = torch.tensor([[[10.0, 50.0, 90.0]] * horizon])
    mock_model.predict.return_value = fake_preds

    # We need to mock TimeSeriesDataSet because it requires specific column types/structures
    # that are hard to fake perfectly without real data setup.
    # However, predict_with_tft calls prepare_training_data which calls TransactionLoader.
    # We can rely on the real trainer logic if it works, or mock it if complex.
    # The real trainer logic works on simple DFs.

    # One issue: TimeSeriesDataSet inside prediction might verify columns.
    # We'll try running it. If TimeSeriesDataSet fails validation, we might mock it.

    with patch("packages.forecasting.inference.TimeSeriesDataSet") as mock_ts_cls:
        # Mock dataset instance
        mock_ds = MagicMock()
        mock_ts_cls.from_dataset.return_value = mock_ds
        mock_ds.to_dataloader.return_value = MagicMock()

        # We also need model.dataset_parameters
        mock_model.dataset_parameters = {}

        result = predict_with_tft(mock_model, df, horizon=30)

        assert "forecast" in result
        forecast = result["forecast"]
        assert len(forecast) == 30
        assert forecast[0]["p10"] == 10.0
        assert forecast[0]["p50"] == 50.0
        assert forecast[0]["p90"] == 90.0
