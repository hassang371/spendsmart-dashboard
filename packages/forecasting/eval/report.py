"""RFC-006 §7 — threshold evaluation + markdown report rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# RFC-006 §7 absolute gates (per RFC-003/RFC-005 success metrics).
DEFAULT_THRESHOLDS: dict[str, float] = {
    "p50_mape_max": 0.10,
    "coverage_min": 0.80,
    "calibration_error_max": 0.05,
}

# Relative regression guards (B vs A).
DEFAULT_RELATIVE_THRESHOLDS: dict[str, float] = {
    "mape_regression_max_pp": 0.05,
    "coverage_regression_max_pp": 0.05,
}


def evaluate_thresholds(
    metrics: dict[str, Any],
    thresholds: dict[str, float] | None = None,
) -> dict[str, bool]:
    """Apply absolute gates to a metrics rollup.

    Args:
        metrics:    Aggregated run metrics; must contain
            ``p50_mape``, ``coverage``, ``calibration_error``.
        thresholds: Optional override for ``DEFAULT_THRESHOLDS``.

    Returns:
        ``{criterion_name: passed?}`` per RFC-006 §7.
    """
    th = thresholds or DEFAULT_THRESHOLDS
    p50 = float(metrics.get("p50_mape", float("inf")))
    cov = float(metrics.get("coverage", 0.0))
    calib = float(metrics.get("calibration_error", float("inf")))

    return {
        "p50_mape_within_threshold": p50 <= th["p50_mape_max"],
        "coverage_above_threshold": cov >= th["coverage_min"],
        "calibration_error_within_threshold": calib <= th["calibration_error_max"],
    }


def render_markdown(
    metrics: dict[str, Any],
    threshold_results: dict[str, bool],
    output_path: Path | str,
    *,
    title: str = "Walk-Forward Evaluation Report",
    diff_against: dict[str, Any] | None = None,
) -> None:
    """Render a markdown report to ``output_path``.

    Layout (per RFC-006 §7):
        1. Title + metadata header
        2. Summary table (mean / median / p95 if present)
        3. Threshold pass/fail block
        4. Optional A vs B comparison block when ``diff_against`` provided
        5. Per-fold table (compact preview, first 20 rows)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Config: `{metrics.get('config_name', 'unknown')}`")
    lines.append(f"- Window: `{metrics.get('window', 'unknown')}`")
    lines.append(f"- Seed: `{metrics.get('seed', 'unknown')}`")
    lines.append(f"- Total folds: {metrics.get('n_folds', 0)}")
    lines.append(f"- Users: {metrics.get('n_users', 0)}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| P50 MAPE | {metrics.get('p50_mape', float('nan')):.4f} |")
    lines.append(f"| Pinball loss (mean) | {metrics.get('pinball_loss_mean', float('nan')):.4f} |")
    lines.append(f"| P10–P90 coverage | {metrics.get('coverage', float('nan')):.4f} |")
    lines.append(f"| Calibration error | {metrics.get('calibration_error', float('nan')):.4f} |")
    lines.append(f"| Mean interval width | {metrics.get('interval_width', float('nan')):.4f} |")
    lines.append("")

    lines.append("## Thresholds (absolute gates)")
    lines.append("")
    lines.append("| Criterion | Result |")
    lines.append("|---|---|")
    for criterion, passed in threshold_results.items():
        symbol = "PASS" if passed else "FAIL"
        lines.append(f"| {criterion} | {symbol} |")
    lines.append("")

    if diff_against is not None:
        lines.append("## Diff vs baseline")
        lines.append("")
        lines.append(f"- Baseline config: `{diff_against.get('config_name', 'unknown')}`")
        delta_mape = float(metrics.get("p50_mape", 0.0)) - float(diff_against.get("p50_mape", 0.0))
        delta_cov = float(metrics.get("coverage", 0.0)) - float(diff_against.get("coverage", 0.0))
        lines.append(f"- Δ P50 MAPE: {delta_mape:+.4f}")
        lines.append(f"- Δ coverage: {delta_cov:+.4f}")
        lines.append("")

    folds = metrics.get("folds", [])
    if folds:
        lines.append("## Per-fold (first 20)")
        lines.append("")
        lines.append("| user_id | fold_idx | window | train_end | mape | coverage |")
        lines.append("|---|---|---|---|---|---|")
        for fold in folds[:20]:
            lines.append(
                f"| {fold.get('user_id', '')} | {fold.get('fold_idx', '')} | "
                f"{fold.get('window', '')} | {fold.get('train_end', '')} | "
                f"{fold.get('mape', float('nan')):.4f} | "
                f"{fold.get('coverage', float('nan')):.4f} |"
            )
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def render_diff_markdown(
    a_path: Path | str,
    b_path: Path | str,
    output_path: Path | str,
) -> None:
    """CLI ``diff`` entrypoint — load two run JSONs, render an A/B report."""
    with open(a_path, encoding="utf-8") as f:
        a = json.load(f)
    with open(b_path, encoding="utf-8") as f:
        b = json.load(f)

    threshold_results = evaluate_thresholds(b)
    render_markdown(
        b,
        threshold_results,
        output_path,
        title="Walk-Forward A/B Comparison",
        diff_against=a,
    )
