"""Tests for the real train_predict callable wired in scripts/walk_forward_eval.py.

Exercises the full path: aggregate_daily_panel → run_training (mocked at
``Trainer.fit`` to avoid GPU/CPU minutes) → model.predict (mocked) →
(horizon, 7) matrix extraction.

The synthetic transaction history below is TEST-only — never imported
into production code paths.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
import torch

from packages.forecasting.eval.configs import TrainingConfig
from packages.forecasting.eval.metrics import QUANTILE_LEVELS
from scripts.walk_forward_eval import (
    _build_future_panel_rows,
    _extract_quantile_matrix,
    _real_train_predict,
    _train_predict_impl,
)


@pytest.fixture
def tiny_history() -> pd.DataFrame:
    """Synthetic 2-year transaction history — covers all 12 months in
    both training (first n-30 days) and validation (full panel) so the
    panel-aware TimeSeriesDataSet's NaNLabelEncoder sees every month
    category. TEST-only fixture."""
    n_days = 730
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n_days, freq="D")
    amounts = np.full(n_days, -50.0)
    amounts[::30] = 2000.0  # monthly inflow
    amounts += rng.normal(0, 5, size=n_days)
    return pd.DataFrame(
        {
            "date": dates,
            "amount": amounts,
            "category": ["other"] * n_days,
        }
    )


# ---------------------------------------------------------------------------
# _train_predict_impl integration: mocks Trainer.fit + model.predict
# so the test asserts the WIRING (panel build → dataset → predict
# extraction) without paying for an actual TFT training step.
# ---------------------------------------------------------------------------


def test_real_train_predict_returns_horizon_by_seven_matrix(tiny_history: pd.DataFrame) -> None:
    """Shape contract: (horizon, 7) ndarray, one column per RFC-003 quantile.

    Mocks ``Trainer.fit`` (skip the real training step) + ``model.predict``
    (returns a synthetic (n_groups=12, horizon=30, 7) tensor) so the test
    runs in seconds, not minutes.
    """
    config = TrainingConfig(
        name="test-1epoch",
        max_epochs=1,
        patience=1,
        weight_decay=0.0,
        batch_size=64,
        learning_rate=3e-4,
    )

    # Synthetic predict output: 12 groups (one per panel bucket), 30
    # horizon steps, 7 quantiles, all set to 100.0 + small per-quantile
    # offsets so monotonicity holds.
    fake_output = torch.zeros((12, 30, 7))
    for q_idx, q in enumerate(QUANTILE_LEVELS):
        fake_output[:, :, q_idx] = 100.0 + (q - 0.5) * 50.0
    fake_prediction = MagicMock()
    fake_prediction.output = fake_output

    train_predict = _real_train_predict(supabase=None)

    with (
        patch("lightning.pytorch.Trainer.fit", return_value=None),
        patch(
            "pytorch_forecasting.models.temporal_fusion_transformer.TemporalFusionTransformer.predict",
            return_value=fake_prediction,
        ),
    ):
        matrix = train_predict(tiny_history, config, 30)

    assert isinstance(matrix, np.ndarray)
    assert matrix.shape == (30, len(QUANTILE_LEVELS))
    assert np.isfinite(matrix).all()


def test_real_train_predict_quantiles_monotonic(tiny_history: pd.DataFrame) -> None:
    """Quantile columns must be monotonic per row when the model output
    is well-formed (mocked here): p2 ≤ p10 ≤ ... ≤ p98.

    This guards the (horizon, 7) extraction logic — averaging across
    groups must preserve quantile ordering.
    """
    config = TrainingConfig(
        name="test-1epoch",
        max_epochs=1,
        patience=1,
        weight_decay=0.0,
        batch_size=64,
        learning_rate=3e-4,
    )

    fake_output = torch.zeros((12, 30, 7))
    for q_idx, q in enumerate(QUANTILE_LEVELS):
        fake_output[:, :, q_idx] = 100.0 + (q - 0.5) * 50.0
    fake_prediction = MagicMock()
    fake_prediction.output = fake_output

    train_predict = _real_train_predict(supabase=None)
    with (
        patch("lightning.pytorch.Trainer.fit", return_value=None),
        patch(
            "pytorch_forecasting.models.temporal_fusion_transformer.TemporalFusionTransformer.predict",
            return_value=fake_prediction,
        ),
    ):
        matrix = train_predict(tiny_history, config, 30)

    diffs = np.diff(matrix, axis=1)
    assert np.all(diffs >= -1e-6), "quantile columns must be (weakly) monotonic"


# ---------------------------------------------------------------------------
# _real_train_predict picklability — required for parallel fold execution
# ---------------------------------------------------------------------------


def test_real_train_predict_returns_picklable_callable() -> None:
    """The returned callable must be picklable so it can cross the
    ProcessPoolExecutor boundary used by ``run_walk_forward(parallel=N)``.

    Closures capturing the supabase client are NOT picklable — the
    Stage 9 wiring returns the bare top-level ``_train_predict_impl``.
    """
    import pickle

    train_predict = _real_train_predict(supabase=MagicMock())
    pickled = pickle.dumps(train_predict)
    restored = pickle.loads(pickled)
    assert restored is _train_predict_impl


# ---------------------------------------------------------------------------
# _build_future_panel_rows
# ---------------------------------------------------------------------------


def test_build_future_panel_rows_extends_each_bucket(tiny_history: pd.DataFrame) -> None:
    """Future rows must cover horizon days × n_buckets, with time_idx
    monotonically continuing the panel."""
    from packages.forecasting.dataset import TransactionLoader, aggregate_daily_panel

    loader = TransactionLoader(tiny_history)
    panel = aggregate_daily_panel(loader)
    n_buckets = panel["category_bucket"].nunique()

    future = _build_future_panel_rows(panel, horizon=30)

    assert len(future) == n_buckets * 30
    # time_idx continues monotonically per bucket.
    for bucket, group in future.groupby("category_bucket"):
        last_panel_idx = panel[panel["category_bucket"] == bucket]["time_idx"].max()
        first_future_idx = group["time_idx"].min()
        assert first_future_idx == last_panel_idx + 1


# ---------------------------------------------------------------------------
# _extract_quantile_matrix unit tests
# ---------------------------------------------------------------------------


def test_extract_quantile_matrix_from_3d_tensor() -> None:
    """A (1, horizon, 7) tensor reduces to a (horizon, 7) ndarray."""
    tensor = torch.zeros((1, 30, 7))
    tensor[0, :, 3] = 100.0  # plant a value in the p50 column
    matrix = _extract_quantile_matrix(tensor, horizon=30, n_quantiles=7)
    assert matrix.shape == (30, 7)
    assert np.allclose(matrix[:, 3], 100.0)


def test_extract_quantile_matrix_raises_on_wrong_quantile_count() -> None:
    """If pytorch-forecasting changes its output_size, raise loudly."""
    bad_tensor = torch.zeros((1, 30, 5))  # wrong quantile count
    with pytest.raises(ValueError, match="quantile"):
        _extract_quantile_matrix(bad_tensor, horizon=30, n_quantiles=7)


def test_extract_quantile_matrix_raises_on_wrong_horizon() -> None:
    bad_tensor = torch.zeros((1, 25, 7))  # wrong horizon
    with pytest.raises(ValueError, match="horizon"):
        _extract_quantile_matrix(bad_tensor, horizon=30, n_quantiles=7)


def test_extract_quantile_matrix_unwraps_prediction_namedtuple() -> None:
    """pytorch-forecasting's ``Prediction(output, x, ...)`` must unwrap
    transparently."""
    tensor = torch.full((1, 30, 7), 7.0)
    prediction = MagicMock()
    prediction.output = tensor
    matrix = _extract_quantile_matrix(prediction, horizon=30, n_quantiles=7)
    assert matrix.shape == (30, 7)
    assert np.allclose(matrix, 7.0)
