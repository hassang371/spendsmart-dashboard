"""Tests for RFC-006 §4 — TrainingConfig presets."""

from __future__ import annotations

import pytest

from packages.forecasting.eval.configs import (
    DEFAULT,
    GROKKING,
    TrainingConfig,
    resolve_config,
)


def test_default_preset_matches_current_production_hyperparams() -> None:
    """RFC-006 §4 — DEFAULT preserves current production-ish behaviour
    (matches the existing trainer defaults)."""
    assert DEFAULT.name == "default"
    assert DEFAULT.max_epochs == 30
    assert DEFAULT.patience == 5
    assert DEFAULT.weight_decay == 0.0
    assert DEFAULT.batch_size == 64
    assert DEFAULT.learning_rate == pytest.approx(3e-4)


def test_grokking_preset_matches_rfc006() -> None:
    """RFC-006 §4 — GROKKING regime: extended patience + weight decay +
    smaller batch size, higher max epochs."""
    assert GROKKING.name == "grokking"
    assert GROKKING.max_epochs == 150
    assert GROKKING.patience == 50
    assert GROKKING.weight_decay == pytest.approx(1e-4)
    assert GROKKING.batch_size == 16
    assert GROKKING.learning_rate == pytest.approx(3e-4)


def test_training_config_is_frozen() -> None:
    """Presets are immutable so they can be safely shared across folds
    and serialised into run JSON."""
    with pytest.raises(Exception):
        DEFAULT.max_epochs = 999  # type: ignore[misc]


def test_resolve_config_returns_known_preset() -> None:
    assert resolve_config("default") is DEFAULT
    assert resolve_config("grokking") is GROKKING


def test_resolve_config_rejects_unknown() -> None:
    with pytest.raises(KeyError):
        resolve_config("not-a-real-config")


def test_training_config_can_be_constructed_directly() -> None:
    cfg = TrainingConfig(
        name="custom",
        max_epochs=10,
        patience=3,
        weight_decay=1e-5,
        batch_size=32,
        learning_rate=1e-3,
    )
    assert cfg.name == "custom"
    assert cfg.max_epochs == 10
