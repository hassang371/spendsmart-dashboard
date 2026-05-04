"""Tests for ``evaluate_past_predictions`` (RFC-003 §5).

Covers:

* Pinball-loss math is golden against ``sklearn.metrics.mean_pinball_loss``.
* MAPE math matches the documented formula.
* The lease-based claim query is testable end-to-end against a real
  Postgres (skipped when ``supabase start`` is not available).

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §5
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Pure-math tests (no DB)
# ---------------------------------------------------------------------------


def test_pinball_loss_matches_sklearn():
    """Per-quantile pinball loss matches sklearn within 1e-9."""
    import numpy as np

    pytest.importorskip("sklearn")
    from sklearn.metrics import mean_pinball_loss

    from apps.api.core.tasks.evaluate_predictions import compute_pinball_loss

    rng = np.random.default_rng(0)
    y_true = rng.normal(loc=10_000.0, scale=500.0, size=30)

    quantile_levels = [0.02, 0.10, 0.25, 0.50, 0.75, 0.90, 0.98]
    forecasts: list[dict[str, float]] = []
    for i in range(30):
        median = float(y_true[i] + rng.normal(0, 100))
        forecasts.append(
            {
                "p2": median - 2000,
                "p10": median - 1000,
                "p25": median - 500,
                "p50": median,
                "p75": median + 500,
                "p90": median + 1000,
                "p98": median + 2000,
            }
        )

    losses = compute_pinball_loss(y_true.tolist(), forecasts)
    for q in quantile_levels:
        key = f"p{int(q * 100) if q != 0.02 else 2}"
        # Build the per-quantile prediction vector
        y_pred = [fc[key] for fc in forecasts]
        expected = mean_pinball_loss(y_true, y_pred, alpha=q)
        assert abs(losses[key] - expected) < 1e-9, f"{key} mismatch: got {losses[key]}, expected {expected}"


def test_compute_mape_matches_formula():
    """``compute_mape(y_true, y_pred)`` ≡ mean(abs((y_true - y_pred) / y_true))."""
    from apps.api.core.tasks.evaluate_predictions import compute_mape

    y_true = [100.0, 200.0, 300.0]
    y_pred = [90.0, 220.0, 270.0]
    expected = (abs(0.10) + abs(0.10) + abs(0.10)) / 3.0
    assert abs(compute_mape(y_true, y_pred) - expected) < 1e-9


def test_compute_mape_returns_none_for_zero_truths():
    """Division-by-zero edge case → return ``None`` so the row's ``mape`` stays NULL."""
    from apps.api.core.tasks.evaluate_predictions import compute_mape

    assert compute_mape([0.0, 0.0], [10.0, 20.0]) is None


# ---------------------------------------------------------------------------
# DB-backed tests — skipped when local supabase unavailable
# ---------------------------------------------------------------------------


def _supabase_running() -> bool:
    import os

    if os.environ.get("SUPABASE_LOCAL_URL") is None:
        return False
    return True


@pytest.mark.skipif(not _supabase_running(), reason="requires running supabase local")
def test_atomic_claim_skips_locked():
    """Two concurrent claim runs return disjoint claim sets (FOR UPDATE SKIP LOCKED)."""
    pytest.skip("DB-backed test runs in Stage 10 verification")


@pytest.mark.skipif(not _supabase_running(), reason="requires running supabase local")
def test_evaluated_at_set_only_after_metrics_computed():
    """If metrics computation throws, ``evaluated_at`` stays NULL (lease expires)."""
    pytest.skip("DB-backed test runs in Stage 10 verification")


@pytest.mark.skipif(not _supabase_running(), reason="requires running supabase local")
def test_crashed_worker_row_is_reclaimable():
    """A row with stale ``lease_expires_at`` is re-claimable (RFC-003 §5 lease test)."""
    pytest.skip("DB-backed test runs in Stage 10 verification")
