"""RFC-006 §2 — walk-forward evaluation CLI.

Subcommands:

    run --users <stratified:N|csv:path|uuid1,uuid2,...>
        --window <expanding|rolling|both>
        --config <default|grokking>
        --output <json_path>

    diff --a <json_a> --b <json_b> --render <markdown_out>

The ``run`` subcommand calls
:func:`packages.forecasting.eval.harness.run_walk_forward` with real
trainer/supabase callables; ``diff`` loads two run JSON artifacts and
writes the comparison markdown via
:func:`packages.forecasting.eval.report.render_diff_markdown`.

This module is offline only — Stage 7 ships the CLI; Stage 9 executes
the first real walk-forward run + research doc.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.forecasting.eval.configs import resolve_config
from packages.forecasting.eval.harness import run_walk_forward
from packages.forecasting.eval.metrics import QUANTILE_LEVELS
from packages.forecasting.eval.report import render_diff_markdown
from packages.forecasting.eval.sampling import select_stratified_users

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts.walk_forward_eval",
        description="RFC-006 walk-forward evaluation harness CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run the walk-forward harness")
    p_run.add_argument(
        "--users",
        required=True,
        help="User selection: stratified:N | csv:path | uuid1,uuid2,... | all",
    )
    p_run.add_argument(
        "--window",
        choices=["expanding", "rolling", "both"],
        default="both",
        help="Fold protocol",
    )
    p_run.add_argument(
        "--config",
        default="default",
        help="Training config preset (default | grokking)",
    )
    p_run.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Output JSON path",
    )
    p_run.add_argument("--horizon", type=int, default=30, help="Prediction horizon (days)")
    p_run.add_argument("--fold-interval", type=int, default=30, help="Days between folds")
    p_run.add_argument("--min-history", type=int, default=90, help="Min training window days")
    p_run.add_argument("--seed", type=int, default=42, help="RNG seed")
    p_run.add_argument(
        "--parallel",
        type=int,
        default=1,
        help=(
            "Number of folds to train in parallel via ProcessPoolExecutor "
            "(RFC-006 §8). Default 1 = sequential. Per-worker BLAS thread "
            "counts are pinned to 1 so fold parallelism is the only "
            "source of CPU multiplexing."
        ),
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="Print user list + fold count + exit; no training",
    )

    p_diff = sub.add_parser("diff", help="Diff two run JSONs into a markdown report")
    p_diff.add_argument("--a", required=True, type=Path, help="Baseline run JSON")
    p_diff.add_argument("--b", required=True, type=Path, help="Comparison run JSON")
    p_diff.add_argument(
        "--render",
        required=True,
        type=Path,
        help="Markdown output path",
    )

    return parser


# ---------------------------------------------------------------------------
# User-selection parsing
# ---------------------------------------------------------------------------


def resolve_user_selection(spec: str, supabase: Any | None = None, seed: int = 42) -> list[str]:
    """Map a CLI ``--users`` argument to a concrete user_id list.

    Supported forms:
        stratified:N → call select_stratified_users(supabase, n=N)
        csv:path     → read newline-separated user_ids from a file
        all          → not supported in v1; raises NotImplementedError
        uuid1,uuid2  → split on commas
    """
    if spec.startswith("stratified:"):
        if supabase is None:
            raise RuntimeError(
                "stratified user selection requires a supabase client; "
                "pass --users csv:path or uuid1,uuid2 for offline runs"
            )
        n = int(spec.split(":", 1)[1])
        return select_stratified_users(supabase, n=n, seed=seed)
    if spec.startswith("csv:"):
        path = Path(spec.split(":", 1)[1])
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if spec == "all":
        raise NotImplementedError("--users all is not supported in v1")
    return [u.strip() for u in spec.split(",") if u.strip()]


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def _real_fetch_history(supabase: Any) -> Any:
    """Build the fetch_history callable used in real runs."""
    from packages.forecasting.trainer import fetch_user_transactions

    def fetch(user_id: str, train_start, train_end):
        df = fetch_user_transactions(supabase, user_id)
        if train_start is not None:
            df = df[df["date"] >= str(train_start)]
        if train_end is not None:
            df = df[df["date"] < str(train_end)]
        return df

    return fetch


def _extract_quantile_matrix(
    raw_output: Any,
    *,
    horizon: int,
    n_quantiles: int = 7,
) -> np.ndarray:
    """Convert a pytorch-forecasting quantile prediction to a (horizon, 7) ndarray.

    pytorch-forecasting's ``model.predict(mode="quantiles", return_x=True)``
    returns a ``Prediction`` namedtuple whose ``.output`` carries a tensor
    of shape ``(batch=1, horizon, n_quantiles)``. With ``return_x=False``
    the tensor itself is returned. This helper accepts either form and
    reduces to a 2-D ndarray indexed by RFC-003 quantile levels.

    Raises:
        ValueError: When the underlying tensor's horizon or quantile-count
            does not match the RFC-003 contract — surfaces an upstream
            pytorch-forecasting shape change loudly rather than silently
            producing wrong forecasts.
    """
    # Unwrap Prediction namedtuple → tensor.
    tensor = getattr(raw_output, "output", raw_output)

    # Strip batch dim if present.
    if hasattr(tensor, "detach"):
        tensor = tensor.detach().cpu()
    arr = np.asarray(tensor, dtype=float)

    if arr.ndim == 3:
        if arr.shape[0] != 1:
            raise ValueError(f"_extract_quantile_matrix: expected batch=1, got batch={arr.shape[0]}")
        arr = arr[0]

    if arr.ndim != 2:
        raise ValueError(f"_extract_quantile_matrix: expected 2D matrix after batch strip, " f"got shape {arr.shape}")

    if arr.shape[0] != horizon:
        raise ValueError(
            f"_extract_quantile_matrix: horizon mismatch — got {arr.shape[0]}, "
            f"expected {horizon}. pytorch-forecasting output shape may have "
            f"changed; investigate model.predict(mode='quantiles')."
        )
    if arr.shape[1] != n_quantiles:
        raise ValueError(
            f"_extract_quantile_matrix: quantile-count mismatch — got "
            f"{arr.shape[1]}, expected {n_quantiles} (RFC-003 quantile set: "
            f"{QUANTILE_LEVELS}). The TFT output_size or QuantileLoss preset "
            f"may have drifted; investigate trainer/tft_model."
        )
    return arr


def _build_future_panel_rows(panel: pd.DataFrame, horizon: int) -> pd.DataFrame:
    """Build a horizon-day extension of ``panel`` for forecasting.

    The panel-aware TFT requires every (date, category_bucket) cell to
    exist for every decoder step. This helper constructs ``horizon`` days
    of future rows for each of the 12 buckets present in ``panel``,
    populates the known calendar features, and zero-fills the unknown
    reals (which are masked out of the decoder by pytorch-forecasting).

    Returns a DataFrame with the same column order as ``panel``.
    """
    last_date = panel["date"].max()
    last_time_idx_per_bucket = panel.groupby("category_bucket")["time_idx"].max().to_dict()
    user_id = panel["user_id"].iloc[0]

    future_dates = pd.date_range(
        start=last_date + pd.Timedelta(days=1),
        periods=horizon,
        freq="D",
    )

    # Carry forward the historical payday day-of-month set (RFC-005 parity
    # with inference.py legacy single-series handling).
    payday_doms = set(panel.loc[panel["is_payday"].astype(str) == "1", "date"].dt.day.unique().tolist())

    rows: list[pd.DataFrame] = []
    for bucket in panel["category_bucket"].unique():
        last_idx = int(last_time_idx_per_bucket[bucket])
        rows.append(
            pd.DataFrame(
                {
                    "date": future_dates,
                    "user_id": user_id,
                    "category_bucket": bucket,
                    "bucket_total": 0.0,
                    "daily_income": 0.0,
                    "daily_spend": 0.0,
                    "closing_balance": 0.0,
                    "scheduled_event_amount": 0.0,
                    "is_payday": pd.Series(
                        ["1" if d.day in payday_doms else "0" for d in future_dates],
                        dtype="object",
                    ),
                    "day_of_week": future_dates.dayofweek.astype(str),
                    "day_of_month": future_dates.day.astype(str),
                    "month": future_dates.month.astype(str),
                    "time_idx": np.arange(last_idx + 1, last_idx + 1 + horizon, dtype=np.int64),
                    "group_id": user_id,
                }
            )
        )

    future = pd.concat(rows, ignore_index=True)
    # Match dtypes of the training panel — categorical columns must use
    # the same category set as the panel to avoid encoder KeyErrors.
    for cat_col in ("is_payday", "day_of_week", "day_of_month", "month"):
        if cat_col in panel.columns:
            cats = panel[cat_col].cat.categories if hasattr(panel[cat_col], "cat") else None
            if cats is not None:
                future[cat_col] = pd.Categorical(future[cat_col], categories=cats)
            else:
                future[cat_col] = future[cat_col].astype("category")
    return future[panel.columns.tolist()]


def _train_predict_impl(history: pd.DataFrame, config: Any, horizon: int) -> np.ndarray:
    """Train a fresh TFT on ``history`` and return a (horizon, 7) quantile matrix.

    Top-level function so it is picklable across the ProcessPoolExecutor
    boundary used when ``--parallel N`` > 1. Steps:

        1. ``aggregate_daily_panel(loader)`` → category-level panel
        2. ``trainer.run_training(panel, **config kwargs)``
        3. Build ``horizon``-day future rows (zero-filled unknown reals)
        4. ``model.predict(loader, mode="quantiles", return_x=True)``
        5. ``_extract_quantile_matrix(raw)`` → (horizon, 7) ndarray

    The ``horizon`` argument MUST match the trainer's
    ``MAX_PREDICTION_LENGTH`` (currently 30 — LLD 009). The TFT was
    trained at a fixed prediction length and pytorch-forecasting clips
    decoder steps to that length; passing horizon ≠ 30 raises in
    ``_extract_quantile_matrix``.
    """
    # Local imports so the harness module can be imported in environments
    # without torch / pytorch-forecasting (e.g. lightweight CI lanes).
    from pytorch_forecasting import TimeSeriesDataSet

    from packages.forecasting.dataset import (
        TransactionLoader,
        aggregate_daily_panel,
    )
    from packages.forecasting.trainer import run_training

    if history is None or len(history) == 0:
        raise ValueError("_train_predict_impl: empty history DataFrame")

    # Step 1 — aggregate to RFC-005 panel.
    loader = TransactionLoader(history)
    panel = aggregate_daily_panel(loader)
    if panel.empty:
        raise ValueError("_train_predict_impl: aggregate_daily_panel returned empty")

    # Step 2 — train.
    _trainer, model, training_dataset = run_training(
        panel,
        max_epochs=config.max_epochs,
        early_stop_patience=config.patience,
        weight_decay=config.weight_decay,
        batch_size=config.batch_size,
        learning_rate=config.learning_rate,
    )

    # Step 3 — append future rows so the decoder window covers
    # [train_end, train_end + horizon).
    future_rows = _build_future_panel_rows(panel, horizon)
    combined = pd.concat([panel, future_rows], ignore_index=True)
    combined = combined.sort_values(["category_bucket", "time_idx"]).reset_index(drop=True)

    # Step 4 — build a prediction dataset over the combined panel;
    # ``predict=True`` clips to the last encoder window per group,
    # whose decoder now sits over the future rows.
    pred_ds = TimeSeriesDataSet.from_dataset(
        training_dataset,
        combined,
        predict=True,
        stop_randomization=True,
    )
    pred_dl = pred_ds.to_dataloader(train=False, batch_size=1, num_workers=0)

    raw = model.predict(pred_dl, mode="quantiles", return_x=True)

    # Step 5 — reduce.
    # pytorch-forecasting's panel mode emits one prediction per group.
    # The harness scores the whole-account closing balance; the panel
    # has 12 groups but every group carries the same closing-balance
    # target, so we average across groups to recover the account-level
    # forecast trajectory.
    tensor = getattr(raw, "output", raw)
    if hasattr(tensor, "detach"):
        tensor = tensor.detach().cpu()
    arr = np.asarray(tensor, dtype=float)
    if arr.ndim == 3 and arr.shape[0] > 1:
        arr = arr.mean(axis=0, keepdims=True)
    return _extract_quantile_matrix(arr, horizon=horizon, n_quantiles=len(QUANTILE_LEVELS))


def _real_train_predict(supabase: Any) -> Any:
    """Return the top-level train_predict callable (Stage 9 wiring).

    Note: ``supabase`` is unused — training does not need DB access; the
    harness pre-fetches history via ``fetch_history`` on the main process.
    The kwarg is retained for API symmetry with ``_real_fetch_history``
    and ``_real_fetch_actuals``. Returning the bare top-level function
    (not a closure) keeps it picklable across the ProcessPoolExecutor
    boundary used when ``--parallel`` > 1.
    """
    return _train_predict_impl


def _real_fetch_actuals(supabase: Any) -> Any:
    """Return the fetch_actuals callable used in real runs.

    Inputs to the returned callable: ``(user_id, test_start, test_end)``
    where the dates are ``datetime.date`` instances. Returns a 1-D NumPy
    array of length ``(test_end - test_start).days`` carrying the actual
    closing-balance trajectory for each day in ``[test_start, test_end)``.

    Closing balance is derived from the same ``TransactionLoader.aggregate_daily``
    logic the trainer uses, so train and eval ground-truth are
    pipeline-consistent (RFC-006 §3).
    """

    def _fetch_actuals(user_id: str, test_start: Any, test_end: Any) -> np.ndarray:
        from packages.forecasting.dataset import TransactionLoader

        start_str = str(test_start)
        end_str = str(test_end)

        response = (
            supabase.table("transactions")
            .select("transaction_date, amount")
            .eq("user_id", user_id)
            .gte("transaction_date", start_str)
            .lte("transaction_date", end_str)
            .order("transaction_date", desc=False)
            .limit(50_000)
            .execute()
        )
        rows = response.data or []
        horizon_days = (pd.to_datetime(end_str) - pd.to_datetime(start_str)).days

        if not rows:
            return np.zeros(horizon_days, dtype=float)

        df = pd.DataFrame(rows)
        df = df.rename(columns={"transaction_date": "date"})
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

        loader = TransactionLoader(df)
        # aggregate_daily reindexes to [start, end] inclusive; we slice
        # to [start, end) to align with harness fold semantics where
        # test_end is exclusive.
        end_inclusive = pd.to_datetime(end_str) - pd.Timedelta(days=1)
        daily = loader.aggregate_daily(
            start_date=pd.to_datetime(start_str),
            end_date=end_inclusive,
        )
        balances = daily["closing_balance"].to_numpy(dtype=float)
        # Defensive: if reindex yielded a different length, pad/truncate.
        if balances.shape[0] != horizon_days:
            out = np.zeros(horizon_days, dtype=float)
            n = min(balances.shape[0], horizon_days)
            out[:n] = balances[:n]
            return out
        return balances

    return _fetch_actuals


def cmd_run(args: argparse.Namespace, supabase: Any | None = None) -> int:
    """Execute the ``run`` subcommand."""
    config = resolve_config(args.config)
    user_ids = resolve_user_selection(args.users, supabase=supabase, seed=args.seed)

    logger.info(
        "walk_forward_eval run config=%s window=%s users=%d output=%s",
        config.name,
        args.window,
        len(user_ids),
        args.output,
    )

    if args.dry_run:
        print(f"Config: {config.name}")
        print(f"Window: {args.window}")
        print(f"Users: {len(user_ids)}")
        for uid in user_ids:
            print(f"  - {uid}")
        print(f"Horizon: {args.horizon} days, fold interval: {args.fold_interval}")
        return 0

    if supabase is None:
        raise RuntimeError(
            "cmd_run requires a supabase client to wire the real harness "
            "callables. The Stage 7 CLI ships the contract; Stage 9 will "
            "supply the production injector."
        )

    summary = run_walk_forward(
        user_ids=user_ids,
        window=args.window,
        config=config,
        output_path=args.output,
        fetch_history=_real_fetch_history(supabase),
        train_predict=_real_train_predict(supabase),
        fetch_actuals=_real_fetch_actuals(supabase),
        horizon=args.horizon,
        fold_interval_days=args.fold_interval,
        min_history_days=args.min_history,
        seed=args.seed,
        parallel=args.parallel,
    )

    print(f"Wrote {args.output}")
    print(f"  n_folds={summary['n_folds']} n_users={summary['n_users']}")
    print(
        f"  p50_mape={summary['p50_mape']:.4f} "
        f"coverage={summary['coverage']:.4f} "
        f"calibration_error={summary['calibration_error']:.4f}"
    )
    return 0


def cmd_diff(args: argparse.Namespace) -> int:
    """Execute the ``diff`` subcommand."""
    render_diff_markdown(args.a, args.b, args.render)
    print(f"Wrote {args.render}")
    return 0


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None, supabase: Any | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.command == "run":
        return cmd_run(args, supabase=supabase)
    if args.command == "diff":
        return cmd_diff(args)
    parser.error(f"Unknown command: {args.command}")
    return 1  # unreachable


if __name__ == "__main__":  # pragma: no cover — CLI entry
    sys.exit(main())
