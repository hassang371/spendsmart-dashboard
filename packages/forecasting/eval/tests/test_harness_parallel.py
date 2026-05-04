"""Tests for RFC-006 §8 — parallel fold execution in run_walk_forward.

Validates that ``run_walk_forward(parallel=N)`` runs folds across a
process pool while preserving deterministic output ordering.

These tests use only synthetic test fixtures — no synthetic data is
introduced into production code paths.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from packages.forecasting.eval.configs import DEFAULT
from packages.forecasting.eval.harness import run_walk_forward
from packages.forecasting.eval.metrics import QUANTILE_LEVELS

# Top-level helpers — must be picklable to cross the ProcessPoolExecutor
# boundary. Closures defined inside test bodies cannot be pickled.


def _two_user_history(user_id: str, train_start, train_end) -> pd.DataFrame:
    """Synthetic 200-day history per user — TEST-only, never imported by
    production code."""
    dates = pd.date_range("2024-01-01", periods=200, freq="D")
    return pd.DataFrame({"date": dates, "amount": np.linspace(0.0, 100.0, 200)})


def _deterministic_train_predict(history: pd.DataFrame, config, horizon: int) -> np.ndarray:
    """Returns a fixed (horizon, 7) matrix derived only from history hash.

    Determinism: identical history → identical forecast, regardless of
    process / fold completion order.
    """
    centre = float(history["amount"].sum() % 100.0) + 50.0
    matrix = np.stack(
        [np.full(horizon, centre + (q - 0.5) * 20.0) for q in QUANTILE_LEVELS],
        axis=1,
    )
    return matrix


def _deterministic_actuals(user_id: str, test_start: date, test_end: date) -> np.ndarray:
    horizon = (test_end - test_start).days
    return np.full(horizon, 52.0)


def test_run_walk_forward_parallel_two_workers_matches_sequential(
    tmp_path: Path,
) -> None:
    """parallel=2 must produce the same fold results as parallel=1, in
    the same deterministic order.
    """
    seq_out = tmp_path / "seq.json"
    par_out = tmp_path / "par.json"

    seq_summary = run_walk_forward(
        user_ids=["user-a", "user-b"],
        window="expanding",
        config=DEFAULT,
        output_path=seq_out,
        fetch_history=_two_user_history,
        train_predict=_deterministic_train_predict,
        fetch_actuals=_deterministic_actuals,
        horizon=30,
        fold_interval_days=30,
        min_history_days=90,
        seed=42,
        parallel=1,
    )

    par_summary = run_walk_forward(
        user_ids=["user-a", "user-b"],
        window="expanding",
        config=DEFAULT,
        output_path=par_out,
        fetch_history=_two_user_history,
        train_predict=_deterministic_train_predict,
        fetch_actuals=_deterministic_actuals,
        horizon=30,
        fold_interval_days=30,
        min_history_days=90,
        seed=42,
        parallel=2,
    )

    # Same number of folds + same aggregate metrics.
    assert seq_summary["n_folds"] == par_summary["n_folds"]
    assert seq_summary["n_folds"] >= 2  # at least one fold per user
    assert seq_summary["p50_mape"] == par_summary["p50_mape"]
    assert seq_summary["coverage"] == par_summary["coverage"]

    # Deterministic fold ordering — sorted by (user_id, fold_idx, window).
    seq_keys = [(f["user_id"], f["window"], f["fold_idx"]) for f in seq_summary["folds"]]
    par_keys = [(f["user_id"], f["window"], f["fold_idx"]) for f in par_summary["folds"]]
    assert seq_keys == par_keys

    # Fold ordering must be lexicographically sorted by (user_id, window, fold_idx).
    assert par_keys == sorted(par_keys)


def test_run_walk_forward_parallel_each_fold_runs_once(tmp_path: Path) -> None:
    """Every (user, window, fold) tuple must appear exactly once."""
    out_path = tmp_path / "par.json"
    summary = run_walk_forward(
        user_ids=["user-a", "user-b"],
        window="expanding",
        config=DEFAULT,
        output_path=out_path,
        fetch_history=_two_user_history,
        train_predict=_deterministic_train_predict,
        fetch_actuals=_deterministic_actuals,
        horizon=30,
        fold_interval_days=30,
        min_history_days=90,
        seed=42,
        parallel=2,
    )

    keys = [(f["user_id"], f["window"], f["fold_idx"]) for f in summary["folds"]]
    assert len(keys) == len(set(keys)), "duplicate folds detected"


def test_run_walk_forward_parallel_default_is_sequential(tmp_path: Path) -> None:
    """parallel kwarg defaults to 1 — no behavioural change vs. Stage 7."""
    out_path = tmp_path / "default.json"
    summary = run_walk_forward(
        user_ids=["user-a"],
        window="expanding",
        config=DEFAULT,
        output_path=out_path,
        fetch_history=_two_user_history,
        train_predict=_deterministic_train_predict,
        fetch_actuals=_deterministic_actuals,
        horizon=30,
        seed=42,
        # no parallel kwarg → default 1
    )
    assert summary["n_folds"] >= 1
