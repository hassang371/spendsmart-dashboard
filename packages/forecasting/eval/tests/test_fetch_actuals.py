"""Tests for the real fetch_actuals callable wired in scripts/walk_forward_eval.py.

The harness invokes ``fetch_actuals(user_id, test_start, test_end)`` and
expects a NumPy array of length ``(test_end - test_start).days`` matching
the actual closing-balance trajectory.

Real Supabase is mocked here — these tests only assert SQL filter
correctness and the closing-balance derivation logic.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import numpy as np

from scripts.walk_forward_eval import _real_fetch_actuals


def _mock_supabase_with_rows(rows: list[dict]) -> MagicMock:
    """Build a chained-mock supabase client that returns ``rows``.

    The chain mirrors the production Supabase Python client:
        client.table(...).select(...).eq(...).gte(...).lte(...)
              .order(...).limit(...).execute()
    """
    client = MagicMock()
    chain = client.table.return_value
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.lte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    response = MagicMock()
    response.data = rows
    chain.execute.return_value = response
    return client


def test_fetch_actuals_returns_horizon_length_array() -> None:
    """Length of returned array == (test_end - test_start).days."""
    rows = [
        {"transaction_date": "2024-06-01", "amount": 1000.0},
        {"transaction_date": "2024-06-02", "amount": -200.0},
        {"transaction_date": "2024-06-05", "amount": 500.0},
    ]
    supabase = _mock_supabase_with_rows(rows)
    fetch_actuals = _real_fetch_actuals(supabase)

    test_start = date(2024, 6, 1)
    test_end = date(2024, 6, 8)  # 7-day horizon
    actuals = fetch_actuals("user-1", test_start, test_end)

    assert isinstance(actuals, np.ndarray)
    assert actuals.shape == (7,), f"expected shape (7,), got {actuals.shape}"


def test_fetch_actuals_drives_correct_supabase_filter() -> None:
    """fetch_actuals must filter by user_id + date range, ordered ascending."""
    rows = [{"transaction_date": "2024-06-01", "amount": 100.0}]
    supabase = _mock_supabase_with_rows(rows)
    fetch_actuals = _real_fetch_actuals(supabase)

    fetch_actuals("user-1", date(2024, 6, 1), date(2024, 6, 8))

    # Inspect the chain mock for the right filter calls.
    chain = supabase.table.return_value
    supabase.table.assert_called_with("transactions")
    chain.eq.assert_called_with("user_id", "user-1")
    # date filter must cover the test window
    chain.gte.assert_called()
    chain.lte.assert_called()
    chain.order.assert_called_with("transaction_date", desc=False)


def test_fetch_actuals_closing_balance_is_cumulative_net() -> None:
    """closing_balance[i] == cumulative net (income - spend) up to day i.

    For a single 1000-rupee inflow on day 0 and no other activity, the
    closing-balance trajectory is [1000.0, 1000.0, 1000.0, ...].
    """
    rows = [{"transaction_date": "2024-06-01", "amount": 1000.0}]
    supabase = _mock_supabase_with_rows(rows)
    fetch_actuals = _real_fetch_actuals(supabase)

    actuals = fetch_actuals("user-1", date(2024, 6, 1), date(2024, 6, 4))
    # 3-day horizon, all carrying the 1000 deposit forward.
    assert actuals.shape == (3,)
    assert np.allclose(actuals, [1000.0, 1000.0, 1000.0])


def test_fetch_actuals_empty_rows_returns_zeros() -> None:
    """When the user has no transactions in the window, return zero-filled
    array of the requested horizon (graceful degradation)."""
    supabase = _mock_supabase_with_rows([])
    fetch_actuals = _real_fetch_actuals(supabase)

    actuals = fetch_actuals("user-1", date(2024, 6, 1), date(2024, 6, 4))
    assert actuals.shape == (3,)
    assert np.allclose(actuals, [0.0, 0.0, 0.0])
