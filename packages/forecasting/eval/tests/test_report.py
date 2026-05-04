"""Tests for RFC-006 §7 — threshold evaluator + markdown report."""

from __future__ import annotations

import json
from pathlib import Path

from packages.forecasting.eval.report import (
    DEFAULT_THRESHOLDS,
    evaluate_thresholds,
    render_diff_markdown,
    render_markdown,
)

# ---------------------------------------------------------------------------
# evaluate_thresholds
# ---------------------------------------------------------------------------


def test_evaluate_thresholds_all_pass() -> None:
    metrics = {"p50_mape": 0.08, "coverage": 0.85, "calibration_error": 0.03}
    out = evaluate_thresholds(metrics)
    assert out == {
        "p50_mape_within_threshold": True,
        "coverage_above_threshold": True,
        "calibration_error_within_threshold": True,
    }


def test_evaluate_thresholds_all_fail() -> None:
    metrics = {"p50_mape": 0.20, "coverage": 0.50, "calibration_error": 0.15}
    out = evaluate_thresholds(metrics)
    assert all(v is False for v in out.values())


def test_evaluate_thresholds_boundary() -> None:
    """Thresholds use ≤/≥, so exact boundary values must PASS."""
    metrics = {
        "p50_mape": DEFAULT_THRESHOLDS["p50_mape_max"],
        "coverage": DEFAULT_THRESHOLDS["coverage_min"],
        "calibration_error": DEFAULT_THRESHOLDS["calibration_error_max"],
    }
    out = evaluate_thresholds(metrics)
    assert out["p50_mape_within_threshold"] is True
    assert out["coverage_above_threshold"] is True
    assert out["calibration_error_within_threshold"] is True


def test_evaluate_thresholds_accepts_custom_thresholds() -> None:
    metrics = {"p50_mape": 0.05, "coverage": 0.99, "calibration_error": 0.01}
    custom = {"p50_mape_max": 0.04, "coverage_min": 0.99, "calibration_error_max": 0.02}
    out = evaluate_thresholds(metrics, custom)
    assert out["p50_mape_within_threshold"] is False  # 0.05 > 0.04
    assert out["coverage_above_threshold"] is True  # 0.99 == 0.99
    assert out["calibration_error_within_threshold"] is True


# ---------------------------------------------------------------------------
# render_markdown
# ---------------------------------------------------------------------------


def _sample_metrics() -> dict:
    return {
        "config_name": "default",
        "window": "expanding",
        "seed": 42,
        "n_folds": 3,
        "n_users": 1,
        "p50_mape": 0.142,
        "pinball_loss_mean": 12.34,
        "coverage": 0.81,
        "calibration_error": 0.045,
        "interval_width": 25.0,
        "folds": [
            {
                "user_id": "u1",
                "fold_idx": 0,
                "window": "expanding",
                "train_end": "2024-04-01",
                "mape": 0.10,
                "coverage": 0.85,
            },
            {
                "user_id": "u1",
                "fold_idx": 1,
                "window": "expanding",
                "train_end": "2024-05-01",
                "mape": 0.18,
                "coverage": 0.78,
            },
        ],
    }


def test_render_markdown_writes_expected_sections(tmp_path: Path) -> None:
    metrics = _sample_metrics()
    threshold_results = evaluate_thresholds(metrics)
    out_path = tmp_path / "report.md"
    render_markdown(metrics, threshold_results, out_path)

    text = out_path.read_text()
    # Header + metadata
    assert "# Walk-Forward Evaluation Report" in text
    assert "default" in text
    assert "expanding" in text
    assert "42" in text
    # Summary table
    assert "P50 MAPE" in text
    assert "0.1420" in text or "0.142" in text
    # Threshold section
    assert "Thresholds" in text
    assert "p50_mape_within_threshold" in text
    # Per-fold rows
    assert "u1" in text


def test_render_markdown_diff_block_present_when_baseline_provided(tmp_path: Path) -> None:
    metrics = _sample_metrics()
    baseline = {**metrics, "config_name": "grokking", "p50_mape": 0.18, "coverage": 0.74}
    out_path = tmp_path / "diff.md"
    render_markdown(
        metrics,
        evaluate_thresholds(metrics),
        out_path,
        diff_against=baseline,
        title="A/B Diff",
    )
    text = out_path.read_text()
    assert "A/B Diff" in text
    assert "Diff vs baseline" in text
    assert "grokking" in text


def test_render_markdown_handles_empty_folds(tmp_path: Path) -> None:
    metrics = _sample_metrics()
    metrics["folds"] = []
    out_path = tmp_path / "empty_folds.md"
    render_markdown(metrics, evaluate_thresholds(metrics), out_path)
    # Doesn't raise; the per-fold section is omitted.
    text = out_path.read_text()
    assert "Per-fold" not in text


def test_render_diff_markdown_loads_two_jsons(tmp_path: Path) -> None:
    a = _sample_metrics()
    a["config_name"] = "default"
    b = {**_sample_metrics(), "config_name": "grokking", "p50_mape": 0.09}
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a_path.write_text(json.dumps(a))
    b_path.write_text(json.dumps(b))

    out = tmp_path / "compare.md"
    render_diff_markdown(a_path, b_path, out)

    text = out.read_text()
    assert "Walk-Forward A/B Comparison" in text
    assert "default" in text
    assert "grokking" in text
