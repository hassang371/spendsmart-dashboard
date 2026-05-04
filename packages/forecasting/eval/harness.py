"""RFC-006 §3 — walk-forward fold loop.

The harness trains a fresh TFT per fold, predicts the next ``horizon``
days, and scores the forecast against actual outcomes. It is offline
only — never writes to ``user_predictions``, never touches the
production cache, never persists checkpoints to Supabase Storage.

Stage 7 ships the skeleton. Stage 9 (per the master plan) executes the
real run on 50 stratified users.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
from collections.abc import Iterable
from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd

from packages.forecasting.eval.configs import TrainingConfig
from packages.forecasting.eval.metrics import (
    QUANTILE_LEVELS,
    calibration_error,
    coverage,
    interval_width,
    mape,
    mean_pinball_loss,
)

logger = logging.getLogger(__name__)


WindowType = Literal["expanding", "rolling", "both"]


def _pool_init() -> None:
    """ProcessPoolExecutor initializer — pin BLAS thread counts to 1.

    pytorch-forecasting + Lightning instantiate a Trainer per fold; each
    Trainer can claim multiple CPU threads via OpenMP / MKL. Pinning to 1
    keeps fold-level parallelism the only source of CPU multiplexing —
    otherwise N pool workers × M BLAS threads can BLAS-block the box.
    """
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_walk_forward(
    user_ids: Iterable[str],
    *,
    window: WindowType,
    config: TrainingConfig,
    output_path: Path | str,
    fetch_history: Any,
    train_predict: Any,
    fetch_actuals: Any,
    horizon: int = 30,
    fold_interval_days: int = 30,
    min_history_days: int = 90,
    seed: int = 42,
    parallel: int = 1,
) -> dict[str, Any]:
    """Run the walk-forward harness across a set of users.

    Args:
        user_ids:      Users to evaluate.
        window:        ``"expanding"``, ``"rolling"``, or ``"both"``.
        config:        Hyperparameter bundle (one of
            :data:`~packages.forecasting.eval.configs.DEFAULT` or
            :data:`~packages.forecasting.eval.configs.GROKKING`, or any
            user-supplied :class:`TrainingConfig`).
        output_path:   JSON path to write the run summary + per-fold rows.
        fetch_history: Callable ``(user_id, train_start, train_end) -> pd.DataFrame``
            returning the user's transaction history within the window.
        train_predict: Callable ``(history_df, config, horizon) -> np.ndarray``
            returning a (horizon, 7) quantile forecast matrix. Must call
            :func:`packages.forecasting.trainer.run_training` internally
            with kwargs derived from ``config``.
        fetch_actuals: Callable ``(user_id, test_start, test_end) -> np.ndarray``
            returning the actual closing-balance trajectory for the
            test window, shape (horizon,).
        horizon:           Prediction horizon in days. Default 30.
        fold_interval_days: Days between fold cursor advances. Default 30.
        min_history_days:  Skip folds with fewer training days than this.
        seed:              RNG seed (recorded in run JSON).
        parallel:          Number of ProcessPoolExecutor workers to run
            folds in parallel. Default 1 = sequential (Stage 7 behaviour).
            When > 1, ``train_predict`` must be picklable (top-level
            function or pickleable callable, not a closure capturing a
            supabase client). I/O callables (``fetch_history``,
            ``fetch_actuals``) always run in the main process, so they
            may capture supabase. Per RFC-006 §8: per-worker BLAS thread
            counts are pinned to 1 so fold parallelism is the only
            source of CPU multiplexing.

    Returns:
        Aggregated run metrics dict with the same keys consumed by
        :func:`packages.forecasting.eval.report.evaluate_thresholds`.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    windows: list[str] = ["expanding", "rolling"] if window == "both" else [window]
    if parallel < 1:
        raise ValueError(f"parallel must be >= 1; got {parallel}")

    # Phase 1 — enumerate fold tasks + pre-fetch I/O on the main process.
    # I/O callables may capture a supabase client (not picklable), so they
    # MUST run in this process. Only ``train_predict`` (which trains a
    # fresh TFT) is dispatched to the worker pool.
    fold_tasks: list[dict[str, Any]] = []
    for user_id in user_ids:
        try:
            user_history = fetch_history(user_id, None, None)
        except Exception as exc:  # pragma: no cover — guarded I/O
            logger.warning("fetch_history failed for %s: %s", user_id, exc)
            continue

        if user_history is None or len(user_history) == 0:
            continue

        history_dates = pd.to_datetime(user_history["date"])
        history_start: date = history_dates.min().date()
        history_end: date = history_dates.max().date()

        for window_name in windows:
            for fold_idx, train_end in enumerate(
                _fold_cursors(
                    start=history_start,
                    end=history_end,
                    fold_interval_days=fold_interval_days,
                    horizon=horizon,
                    window_name=window_name,
                    min_history_days=min_history_days,
                )
            ):
                if window_name == "rolling":
                    train_start = train_end - timedelta(days=365)
                else:
                    train_start = history_start

                test_start = train_end
                test_end = train_end + timedelta(days=horizon)

                try:
                    history = fetch_history(user_id, train_start, train_end)
                    actuals = fetch_actuals(user_id, test_start, test_end)
                except Exception as exc:  # pragma: no cover — defensive
                    logger.warning(
                        "fold I/O failed user=%s window=%s fold=%d: %s",
                        user_id,
                        window_name,
                        fold_idx,
                        exc,
                    )
                    continue

                fold_tasks.append(
                    {
                        "user_id": user_id,
                        "window": window_name,
                        "fold_idx": fold_idx,
                        "train_start": train_start,
                        "train_end": train_end,
                        "test_start": test_start,
                        "test_end": test_end,
                        "history": history,
                        "actuals": actuals,
                    }
                )

    # Phase 2 — run train_predict either sequentially or in a process pool.
    fold_results = _execute_fold_tasks(
        fold_tasks=fold_tasks,
        train_predict=train_predict,
        config=config,
        horizon=horizon,
        parallel=parallel,
    )

    # Phase 3 — sort by (user_id, window, fold_idx) so the JSON is
    # deterministic regardless of fold completion order in the pool.
    fold_results.sort(key=lambda f: (f["user_id"], f["window"], f["fold_idx"]))

    summary = _aggregate(fold_results, config=config, window=window, seed=seed)
    summary["folds"] = fold_results
    output_path.write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")
    return summary


def _execute_fold_tasks(
    *,
    fold_tasks: list[dict[str, Any]],
    train_predict: Any,
    config: TrainingConfig,
    horizon: int,
    parallel: int,
) -> list[dict[str, Any]]:
    """Run each fold's train_predict step and score the result.

    Sequential when ``parallel == 1``; ProcessPoolExecutor with
    ``max_workers=parallel`` and BLAS threads pinned to 1 otherwise.
    """
    if parallel == 1:
        results: list[dict[str, Any]] = []
        for task in fold_tasks:
            row = _train_score_one(task, train_predict, config, horizon)
            if row is not None:
                results.append(row)
        return results

    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=parallel, initializer=_pool_init) as pool:
        future_to_task = {
            pool.submit(_train_score_one, task, train_predict, config, horizon): task for task in fold_tasks
        }
        for future in concurrent.futures.as_completed(future_to_task):
            task = future_to_task[future]
            try:
                row = future.result()
            except Exception as exc:  # pragma: no cover — defensive
                logger.warning(
                    "fold worker failed user=%s window=%s fold=%d: %s",
                    task["user_id"],
                    task["window"],
                    task["fold_idx"],
                    exc,
                )
                continue
            if row is not None:
                results.append(row)
    return results


def _train_score_one(
    task: dict[str, Any],
    train_predict: Any,
    config: TrainingConfig,
    horizon: int,
) -> dict[str, Any] | None:
    """Train + predict + score a single fold task.

    Top-level so it is picklable across the ProcessPoolExecutor boundary.
    """
    try:
        forecast_matrix = train_predict(task["history"], config, horizon)
    except Exception as exc:  # pragma: no cover — defensive
        logger.warning(
            "train_predict failed user=%s window=%s fold=%d: %s",
            task["user_id"],
            task["window"],
            task["fold_idx"],
            exc,
        )
        return None

    metrics = _score_fold(forecast_matrix, task["actuals"])
    return {
        "user_id": task["user_id"],
        "window": task["window"],
        "fold_idx": task["fold_idx"],
        "train_start": task["train_start"].isoformat(),
        "train_end": task["train_end"].isoformat(),
        "test_start": task["test_start"].isoformat(),
        "test_end": task["test_end"].isoformat(),
        **metrics,
    }


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _fold_cursors(
    *,
    start: date,
    end: date,
    fold_interval_days: int,
    horizon: int,
    window_name: str,
    min_history_days: int,
) -> Iterable[date]:
    """Yield ``train_end`` dates per RFC-006 §3 fold protocol."""
    if window_name == "rolling":
        first_train_days = 365
    else:
        first_train_days = max(min_history_days, 3 * fold_interval_days)

    cursor = start + timedelta(days=first_train_days)
    horizon_delta = timedelta(days=horizon)
    while cursor + horizon_delta <= end:
        yield cursor
        cursor = cursor + timedelta(days=fold_interval_days)


def _score_fold(
    forecast_matrix: np.ndarray,
    actuals: np.ndarray,
) -> dict[str, float]:
    """Compute per-fold metrics from a (horizon, 7) forecast matrix."""
    forecast_matrix = np.asarray(forecast_matrix, dtype=float)
    actuals = np.asarray(actuals, dtype=float)

    p50_idx = QUANTILE_LEVELS.index(0.50)
    p10_idx = QUANTILE_LEVELS.index(0.10)
    p90_idx = QUANTILE_LEVELS.index(0.90)

    p50 = forecast_matrix[:, p50_idx]
    p10 = forecast_matrix[:, p10_idx]
    p90 = forecast_matrix[:, p90_idx]

    cov = coverage(actuals, p10, p90)
    calib = calibration_error(forecast_matrix, actuals)
    return {
        "mape": mape(p50, actuals),
        "pinball_loss_mean": mean_pinball_loss(actuals, forecast_matrix),
        "coverage": cov,
        "interval_width": interval_width(p10, p90),
        "calibration_error": float(calib["mean_abs_deviation"]),
    }


def _aggregate(
    folds: list[dict[str, Any]],
    *,
    config: TrainingConfig,
    window: WindowType,
    seed: int,
) -> dict[str, Any]:
    """Roll up per-fold metrics into the run summary consumed by report.py."""
    if not folds:
        return {
            "config_name": config.name,
            "config": asdict(config),
            "window": window,
            "seed": seed,
            "n_folds": 0,
            "n_users": 0,
            "p50_mape": float("nan"),
            "pinball_loss_mean": float("nan"),
            "coverage": float("nan"),
            "calibration_error": float("nan"),
            "interval_width": float("nan"),
        }

    def _mean(key: str) -> float:
        values = [f[key] for f in folds if not np.isnan(f.get(key, float("nan")))]
        return float(np.mean(values)) if values else float("nan")

    return {
        "config_name": config.name,
        "config": asdict(config),
        "window": window,
        "seed": seed,
        "n_folds": len(folds),
        "n_users": len({f["user_id"] for f in folds}),
        "p50_mape": _mean("mape"),
        "pinball_loss_mean": _mean("pinball_loss_mean"),
        "coverage": _mean("coverage"),
        "calibration_error": _mean("calibration_error"),
        "interval_width": _mean("interval_width"),
    }


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
