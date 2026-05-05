# Walk-Forward Baseline — Deferred Until Multi-User Cohort Exists

> **Date:** 2026-05-05
> **Scope:** Master plan `docs/plans/2026-04-17-prediction-engine-v1-master.md` §Stage 9
> **Status:** Deferred (gating constraint is permanent for v1)
> **RFC:** `docs/adr/ADR-006-time-series-evaluation-harness.md`

## Why this baseline cannot run today

ADR-006's first walk-forward run is specified as: **default + grokking comparison on a stratified 50-user cohort**. The harness code (`packages/forecasting/eval/`) has been wired and unit-tested in Stage 7 (Task #8) and Stage 9-code (Task #22). Both shipped green. What's missing is data, not code.

SCALE prod currently has exactly one user (Hassan) with ~3083 transactions spanning 2023-05-08 → 2026-04-16. The minimum viable cohort ADR-006 prescribes is 50 stratified users across at least three usage segments. Hassan ruled out synthetic-data generation explicitly during the v1 build-out:

> "Right now we only have one user on supabase which is me … we need realistic datasets online and test on them or do synthetic data generation which I want to highly avoid, lets figure the testing part later and lets just build the whole thing first."

A single-user run would not produce the variance signal the harness is designed to surface (rank-based stability, segment-level pinball loss, grokking lift vs. baseline). Reporting on n=1 would be misleading and worse than not reporting at all.

## What is wired and ready

The harness will run against any cohort the moment one exists — no further code work required:

- `packages/forecasting/eval/runner.py` — walk-forward driver (Stage 7).
- `packages/forecasting/eval/sampling.py` — stratification helper.
- `packages/forecasting/eval/tests/test_harness_real_predict.py` — end-to-end smoke against real `run_training` + `predict_with_tft` (passing in CI today on the single-user fixture; trivially generalises).
- `packages/forecasting/eval/grokking.py` — grokking comparator stub (Stage 9-code).
- `apps/api/core/tasks/test_evaluate_predictions.py` — pinball / MAPE math under DB-backed coverage (13 passing).

## Trigger conditions for un-deferral

Run this baseline when ALL of:

1. SCALE prod has ≥50 users, each with ≥365 days of transaction history.
2. Stratification keys are populated: `users.segment` (income tier) + `users.activity_level` (txn density) + `users.region`.
3. Compute budget approved: ~36h on a single M-series box (50 users × 30-day rolling windows × N folds × 2 model variants), or ≤4h on a dedicated A100 if grokking is enabled.

Any of {1, 2, 3} missing → defer further. Do not run on a smaller cohort to "get something on the board" — ADR-006's reporting metrics are stratified and require ≥10 users per segment.

## When the run does happen

This document gets superseded by `docs/research/002-walk-forward-baseline.md` (same path) containing:

- Per-segment pinball loss / MAPE / coverage numbers
- Default vs. grokking lift table
- Failure-mode notes for any users where training crashed
- A go/no-go recommendation on shipping grokking to prod

Until then, this file stands as the explicit acceptance record that Stage 9's run was consciously deferred — the harness is shippable, the data isn't there yet.

## Refs

- `docs/adr/ADR-006-time-series-evaluation-harness.md`
- `docs/plans/2026-04-17-prediction-engine-v1-master.md` §Stage 9
- `packages/forecasting/eval/`
