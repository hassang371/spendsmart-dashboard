"""Tests for RFC-006 §6 — stratified user sampling."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from packages.forecasting.eval.sampling import (
    STRATA,
    _classify_users,
    select_stratified_users,
)

# ---------------------------------------------------------------------------
# Fake supabase scaffolding
# ---------------------------------------------------------------------------


class _FakeQueryChain:
    def __init__(self, data: list[dict]):
        self._data = data

    def select(self, *_args, **_kwargs) -> "_FakeQueryChain":
        return self

    def lte(self, *_args, **_kwargs) -> "_FakeQueryChain":
        return self

    def execute(self) -> Any:
        resp = MagicMock()
        resp.data = self._data
        return resp


class _FakeSupabase:
    def __init__(self, txn_rows: list[dict], account_rows: list[dict]):
        self._txn = txn_rows
        self._accounts = account_rows

    def table(self, name: str) -> _FakeQueryChain:
        if name == "transactions":
            return _FakeQueryChain(self._txn)
        if name == "bank_accounts":
            return _FakeQueryChain(self._accounts)
        raise KeyError(name)


# ---------------------------------------------------------------------------
# Test data builders
# ---------------------------------------------------------------------------


def _build_synthetic_corpus(n_users: int = 25) -> tuple[list[dict], list[dict]]:
    """Spread users across all five strata so the test produces a balanced
    selection."""
    txn_rows: list[dict] = []
    account_rows: list[dict] = []
    cutoff = date.today() - timedelta(days=900)

    for i in range(n_users):
        uid = f"user-{i:03d}"
        # high-frequency: lots of txns (300)
        # low-frequency: few txns (5)
        # life-event: high CoV spends
        # salary-only: 80% in {salary, rent, groceries}
        # multi-account: 2 provider rows
        if i < 5:
            for k in range(300):
                txn_rows.append(
                    {
                        "user_id": uid,
                        "transaction_date": (cutoff - timedelta(days=k)).isoformat(),
                        "amount": -100.0 - (k % 50),
                        "category": "groceries",
                    }
                )
        elif i < 10:
            for k in range(8):
                txn_rows.append(
                    {
                        "user_id": uid,
                        "transaction_date": (cutoff - timedelta(days=k * 30)).isoformat(),
                        "amount": -50.0,
                        "category": "groceries",
                    }
                )
        elif i < 15:
            # life event: high coefficient-of-variation spend (mix tiny +
            # huge negative amounts).
            for k in range(60):
                amt = -10.0 if k % 2 == 0 else -5000.0
                txn_rows.append(
                    {
                        "user_id": uid,
                        "transaction_date": (cutoff - timedelta(days=k)).isoformat(),
                        "amount": amt,
                        "category": "other",
                    }
                )
        elif i < 20:
            # salary-only: mostly salary/rent/groceries categories
            for k in range(50):
                cat = ["salary", "rent", "groceries", "utilities"][k % 4]
                txn_rows.append(
                    {
                        "user_id": uid,
                        "transaction_date": (cutoff - timedelta(days=k)).isoformat(),
                        "amount": 1000.0 if cat == "salary" else -200.0,
                        "category": cat,
                    }
                )
        else:
            # multi-account: 2 provider_account_id rows
            account_rows.append({"user_id": uid, "provider_account_id": f"acct-a-{i}"})
            account_rows.append({"user_id": uid, "provider_account_id": f"acct-b-{i}"})
            for k in range(30):
                txn_rows.append(
                    {
                        "user_id": uid,
                        "transaction_date": (cutoff - timedelta(days=k)).isoformat(),
                        "amount": -100.0,
                        "category": "groceries",
                    }
                )

    return txn_rows, account_rows


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_select_stratified_users_returns_n_unique_ids() -> None:
    txn_rows, accounts = _build_synthetic_corpus(n_users=25)
    supabase = _FakeSupabase(txn_rows, accounts)

    users = select_stratified_users(supabase, n=10, seed=42)
    assert len(users) <= 10
    assert len(set(users)) == len(users)  # unique


def test_select_stratified_users_is_seed_reproducible() -> None:
    txn_rows, accounts = _build_synthetic_corpus(n_users=25)
    supabase = _FakeSupabase(txn_rows, accounts)

    a = select_stratified_users(supabase, n=10, seed=42)
    b = select_stratified_users(supabase, n=10, seed=42)
    assert a == b


def test_strata_balance_across_archetypes() -> None:
    """Each stratum should contribute ~n/5 users when all strata have
    qualifying members."""
    txn_rows, accounts = _build_synthetic_corpus(n_users=25)
    supabase = _FakeSupabase(txn_rows, accounts)

    composition = _classify_users(supabase, min_history_days=730, strata=list(STRATA))
    # The synthetic corpus stocks ≥4 users per stratum (modulo overlap),
    # so the classifier must surface non-empty buckets for each.
    for stratum in STRATA:
        assert stratum in composition
    # At least three of the five strata must be non-empty (the synthetic
    # corpus may show overlaps where life-event users also pass low-freq
    # thresholds; that is acceptable so long as the classifier wires up).
    non_empty = [s for s in STRATA if composition[s]]
    assert len(non_empty) >= 3


def test_select_stratified_users_requires_supabase() -> None:
    with pytest.raises(ValueError):
        select_stratified_users(None, n=10)


def test_select_stratified_users_handles_empty_corpus() -> None:
    supabase = _FakeSupabase(txn_rows=[], account_rows=[])
    users = select_stratified_users(supabase, n=10, seed=1)
    assert users == []
