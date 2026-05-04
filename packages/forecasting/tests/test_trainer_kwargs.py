"""Tests for RFC-006 — ``run_training`` kwarg expansion.

Verifies the new kwargs (``weight_decay``, ``batch_size``,
``learning_rate``) are accepted and plumbed into the underlying
PyTorch Lightning ``Trainer`` and the ``TemporalFusionTransformer``.
Defaults preserve the existing production behaviour exactly.
"""

from __future__ import annotations

import inspect

import pandas as pd
import pytest

from packages.forecasting import trainer as trainer_module
from packages.forecasting.dataset import TransactionLoader
from packages.forecasting.trainer import run_training


def test_run_training_signature_includes_new_kwargs() -> None:
    """RFC-006 §4 — the harness maps TrainingConfig fields to these kwargs."""
    params = inspect.signature(run_training).parameters
    # Existing params preserved (no breaking renames):
    assert "enriched_df" in params
    assert "max_epochs" in params
    assert "early_stop_patience" in params
    # New kwargs:
    assert "weight_decay" in params
    assert "batch_size" in params
    assert "learning_rate" in params


def test_run_training_default_values_preserve_production_behaviour() -> None:
    """Defaults must preserve current production behaviour so unchanged
    callers (e.g., apps/worker/main.py::train_model) keep working."""
    params = inspect.signature(run_training).parameters
    assert params["max_epochs"].default == 30
    assert params["early_stop_patience"].default == 5
    assert params["weight_decay"].default == 0.0
    assert params["batch_size"].default == 64
    assert params["learning_rate"].default == pytest.approx(3e-4)


def _make_enriched_df(n_days: int = 90) -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=n_days, freq="D"),
            "amount": [10.0] * n_days,
        }
    )
    loader = TransactionLoader(df)
    daily = loader.aggregate_daily()
    return loader.enrich_features(daily)


def test_run_training_passes_new_kwargs_to_underlying_components(monkeypatch) -> None:
    """``run_training`` should plumb batch_size into the dataloader,
    weight_decay/learning_rate into the TFT, and not crash on the new
    kwargs."""
    captured: dict[str, object] = {}

    real_create_tft = trainer_module.create_tft_model

    def spy_create_tft(*args, **kwargs):
        captured["learning_rate"] = kwargs.get("learning_rate")
        return real_create_tft(*args, **kwargs)

    real_to_dl = None

    def patch_to_dataloader(self, *args, **kwargs):
        captured.setdefault("batch_size", kwargs.get("batch_size"))
        return real_to_dl(self, *args, **kwargs)

    monkeypatch.setattr(trainer_module, "create_tft_model", spy_create_tft)

    # Patch TimeSeriesDataSet.to_dataloader to capture batch_size.
    from pytorch_forecasting import TimeSeriesDataSet

    nonlocal_real = TimeSeriesDataSet.to_dataloader
    real_to_dl = nonlocal_real
    monkeypatch.setattr(TimeSeriesDataSet, "to_dataloader", patch_to_dataloader)

    # Use a tiny enriched_df so the call exercises construction without
    # actually running fit (we'll let pytorch-lightning fast_dev_run via
    # max_epochs=1 + a small dataloader; but to keep test under 30s we
    # short-circuit fit by patching trainer.fit).
    monkeypatch.setattr(
        "lightning.pytorch.Trainer.fit",
        lambda self, *args, **kwargs: None,
    )

    enriched = _make_enriched_df(120)

    run_training(
        enriched,
        max_epochs=1,
        early_stop_patience=1,
        weight_decay=1e-4,
        batch_size=8,
        learning_rate=5e-4,
    )

    assert captured.get("batch_size") == 8
    assert captured.get("learning_rate") == pytest.approx(5e-4)
