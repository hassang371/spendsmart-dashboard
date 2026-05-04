"""Tests for RFC-006 §2 — walk_forward_eval CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.walk_forward_eval import (
    build_parser,
    cmd_diff,
    main,
    resolve_user_selection,
)


def test_parser_run_subcommand_required_flags(tmp_path: Path) -> None:
    parser = build_parser()
    out = tmp_path / "out.json"
    args = parser.parse_args(
        ["run", "--users", "uid-1,uid-2", "--window", "expanding", "--config", "default", "--output", str(out)]
    )
    assert args.command == "run"
    assert args.window == "expanding"
    assert args.config == "default"
    assert args.output == out


def test_parser_diff_subcommand_required_flags(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(["diff", "--a", "a.json", "--b", "b.json", "--render", str(tmp_path / "out.md")])
    assert args.command == "diff"


def test_resolve_user_selection_csv_form() -> None:
    """uuid1,uuid2 form returns a list."""
    out = resolve_user_selection("uid-a,uid-b,uid-c")
    assert out == ["uid-a", "uid-b", "uid-c"]


def test_resolve_user_selection_csv_file_form(tmp_path: Path) -> None:
    csv_file = tmp_path / "users.txt"
    csv_file.write_text("user-1\nuser-2\n\nuser-3\n")
    out = resolve_user_selection(f"csv:{csv_file}")
    assert out == ["user-1", "user-2", "user-3"]


def test_resolve_user_selection_stratified_requires_supabase() -> None:
    with pytest.raises(RuntimeError):
        resolve_user_selection("stratified:50", supabase=None)


def test_resolve_user_selection_all_not_implemented() -> None:
    with pytest.raises(NotImplementedError):
        resolve_user_selection("all")


def test_cmd_diff_renders_markdown(tmp_path: Path) -> None:
    a = {
        "config_name": "default",
        "p50_mape": 0.10,
        "coverage": 0.85,
        "calibration_error": 0.04,
        "pinball_loss_mean": 1.0,
        "interval_width": 5.0,
        "n_folds": 1,
        "n_users": 1,
        "seed": 42,
        "window": "expanding",
        "folds": [],
    }
    b = {**a, "config_name": "grokking", "p50_mape": 0.08}
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a_path.write_text(json.dumps(a))
    b_path.write_text(json.dumps(b))

    output = tmp_path / "diff.md"
    parser = build_parser()
    args = parser.parse_args(["diff", "--a", str(a_path), "--b", str(b_path), "--render", str(output)])
    rc = cmd_diff(args)
    assert rc == 0
    assert output.exists()
    text = output.read_text()
    assert "default" in text
    assert "grokking" in text


def test_main_dispatches_diff(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    a = {
        "config_name": "default",
        "p50_mape": 0.1,
        "coverage": 0.85,
        "calibration_error": 0.03,
        "pinball_loss_mean": 1.0,
        "interval_width": 5.0,
        "n_folds": 1,
        "n_users": 1,
        "seed": 1,
        "window": "expanding",
        "folds": [],
    }
    a_path = tmp_path / "a.json"
    b_path = tmp_path / "b.json"
    a_path.write_text(json.dumps(a))
    b_path.write_text(json.dumps(a))
    out = tmp_path / "out.md"

    rc = main(["diff", "--a", str(a_path), "--b", str(b_path), "--render", str(out)])
    assert rc == 0
    assert out.exists()


def test_main_run_dry_run_prints_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Dry-run does not require a supabase client."""
    out = tmp_path / "run.json"
    rc = main(
        [
            "run",
            "--users",
            "user-a,user-b",
            "--window",
            "expanding",
            "--config",
            "default",
            "--output",
            str(out),
            "--dry-run",
        ]
    )
    assert rc == 0
    captured = capsys.readouterr().out
    assert "user-a" in captured
    assert "user-b" in captured
