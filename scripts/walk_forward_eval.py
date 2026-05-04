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


def _real_train_predict(supabase: Any) -> Any:
    """Build the train_predict callable used in real runs.

    Stage 7 ships the wiring; Stage 9 runs the harness against real data.
    The real implementation would call:
      1. aggregate_daily_panel(history, ...) → panel
      2. trainer.run_training(panel, **config kwargs)
      3. model.predict(...) → (horizon, 7) matrix
    Since this requires a populated DB + Supabase client, we raise
    NotImplementedError when called from a stub-less context. Callers
    in Stage 9 will replace this with the full training pipeline.
    """

    def _train_predict(history, config, horizon):  # pragma: no cover — Stage 9
        raise NotImplementedError(
            "Real train_predict wiring is implemented in Stage 9. "
            "Use the harness via run_walk_forward(...) with explicit "
            "callables for unit testing."
        )

    return _train_predict


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
