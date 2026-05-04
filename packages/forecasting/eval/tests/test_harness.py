"""Tests for RFC-006 §3 — walk-forward harness fold loop.

The harness is exercised via injectable callables so the unit tests
avoid a real TFT training run. A small synthetic smoke test runs a
1-fold loop end-to-end with stub callables (epochs=1) and asserts the
JSON output + threshold evaluator integration.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from packages.forecasting.eval.configs import DEFAULT
from packages.forecasting.eval.harness import _fold_cursors, run_walk_forward
from packages.forecasting.eval.metrics import QUANTILE_LEVELS
from packages.forecasting.eval.report import evaluate_thresholds

# ---------------------------------------------------------------------------
# Fold cursor protocol
# ---------------------------------------------------------------------------


def test_fold_cursors_expanding_starts_at_min_history() -> None:
    """Expanding window starts after at least 90 days (LLD 009 cold-start
    floor)."""
    cursors = list(
        _fold_cursors(
            start=date(2024, 1, 1),
            end=date(2025, 12, 31),
            fold_interval_days=30,
            horizon=30,
            window_name="expanding",
            min_history_days=90,
        )
    )
    assert cursors, "expanding window must yield at least one cursor"
    first_train_days = (cursors[0] - date(2024, 1, 1)).days
    assert first_train_days >= 90


def test_fold_cursors_rolling_starts_at_365_days() -> None:
    """Rolling window starts after a fixed 365-day training set."""
    cursors = list(
        _fold_cursors(
            start=date(2023, 1, 1),
            end=date(2025, 12, 31),
            fold_interval_days=30,
            horizon=30,
            window_name="rolling",
            min_history_days=90,
        )
    )
    assert cursors, "rolling window must yield at least one cursor"
    first_train_days = (cursors[0] - date(2023, 1, 1)).days
    assert first_train_days >= 365


def test_fold_cursors_advances_in_fold_interval() -> None:
    cursors = list(
        _fold_cursors(
            start=date(2024, 1, 1),
            end=date(2025, 12, 31),
            fold_interval_days=30,
            horizon=30,
            window_name="expanding",
            min_history_days=90,
        )
    )
    if len(cursors) >= 2:
        assert (cursors[1] - cursors[0]).days == 30


# ---------------------------------------------------------------------------
# End-to-end synthetic smoke test
# ---------------------------------------------------------------------------


def _stub_history(user_id: str, train_start, train_end) -> pd.DataFrame:
    """Synthetic 200-day history."""
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    return pd.DataFrame({"date": dates, "amount": np.linspace(0.0, 100.0, 200)})


def _stub_train_predict(history: pd.DataFrame, config, horizon: int) -> np.ndarray:
    """Return a (horizon, 7) forecast matrix with quantile-shaped spread.

    The synthetic forecast is centred at 50.0 and spread linearly across
    the 7 quantile levels (so the harness exercises every metric).
    """
    centre = np.full(horizon, 50.0)
    forecast = np.stack([centre + (q - 0.5) * 20.0 for q in QUANTILE_LEVELS], axis=1)
    return forecast


def _stub_actuals(user_id: str, test_start: date, test_end: date) -> np.ndarray:
    """Actuals: same length as horizon, slightly off the centre forecast
    so MAPE is non-zero but bounded."""
    horizon = (test_end - test_start).days
    return np.full(horizon, 52.0)


def test_run_walk_forward_end_to_end_writes_json(tmp_path: Path) -> None:
    """Smoke test: 1 user, expanding window, ≥1 fold → JSON written."""
    output_path = tmp_path / "run.json"

    summary = run_walk_forward(
        user_ids=["user-1"],
        window="expanding",
        config=DEFAULT,
        output_path=output_path,
        fetch_history=_stub_history,
        train_predict=_stub_train_predict,
        fetch_actuals=_stub_actuals,
        horizon=30,
        fold_interval_days=30,
        min_history_days=90,
        seed=42,
    )

    assert output_path.exists()
    on_disk = json.loads(output_path.read_text())

    assert on_disk["config_name"] == "default"
    assert on_disk["seed"] == 42
    assert on_disk["window"] == "expanding"
    assert on_disk["n_folds"] >= 1
    assert "p50_mape" in on_disk
    assert "coverage" in on_disk
    assert "calibration_error" in on_disk
    assert "folds" in on_disk
    assert summary["n_folds"] == on_disk["n_folds"]


def test_run_walk_forward_threshold_evaluator_runs(tmp_path: Path) -> None:
    """The harness output must be consumable by ``evaluate_thresholds``
    without raising, regardless of pass/fail outcome."""
    output_path = tmp_path / "run.json"

    summary = run_walk_forward(
        user_ids=["user-1"],
        window="expanding",
        config=DEFAULT,
        output_path=output_path,
        fetch_history=_stub_history,
        train_predict=_stub_train_predict,
        fetch_actuals=_stub_actuals,
        horizon=30,
        seed=42,
    )

    results = evaluate_thresholds(summary)
    assert "p50_mape_within_threshold" in results
    assert "coverage_above_threshold" in results
    assert "calibration_error_within_threshold" in results
    for v in results.values():
        assert isinstance(v, bool)


def test_run_walk_forward_handles_no_folds(tmp_path: Path) -> None:
    """If a user's history is too short for any fold, the harness must
    still write a valid summary JSON with n_folds=0."""

    def short_history(uid, start, end):
        dates = pd.date_range("2024-01-01", periods=20, freq="D")
        return pd.DataFrame({"date": dates, "amount": [1.0] * 20})

    output_path = tmp_path / "empty.json"
    summary = run_walk_forward(
        user_ids=["user-1"],
        window="expanding",
        config=DEFAULT,
        output_path=output_path,
        fetch_history=short_history,
        train_predict=_stub_train_predict,
        fetch_actuals=_stub_actuals,
        horizon=30,
        seed=42,
    )
    assert summary["n_folds"] == 0
    assert output_path.exists()
