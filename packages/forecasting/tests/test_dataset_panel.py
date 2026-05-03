"""Tests for RFC-005 §3 — aggregate_daily_panel + panel TimeSeriesDataSet."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from packages.forecasting.buckets import CATEGORY_BUCKETS
from packages.forecasting.dataset import (
    TransactionLoader,
    aggregate_daily_panel,
    create_timeseries_dataset,
)
from packages.forecasting.scheduler import (
    RecurrenceRule,
    project_scheduled_cashflows,
)


def _basic_loader(n_days: int = 30) -> TransactionLoader:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for d in dates:
        rows.append({"date": d, "amount": -float(rng.uniform(50, 500)), "category": "Groceries"})
        if d.day == 1:
            rows.append({"date": d, "amount": 50000.0, "category": "Salary"})
    return TransactionLoader(pd.DataFrame(rows))


def test_panel_is_dense_and_has_12_buckets():
    loader = _basic_loader(30)
    panel = aggregate_daily_panel(loader, user_id="u1")

    assert panel["date"].nunique() == 30
    assert panel["category_bucket"].nunique() == 12
    assert len(panel) == 30 * 12

    # Every (date, bucket) pair is present.
    expected_pairs = {(d, b) for d in panel["date"].unique() for b in CATEGORY_BUCKETS}
    actual_pairs = set(zip(panel["date"], panel["category_bucket"]))
    assert expected_pairs == actual_pairs


def test_closing_balance_invariant_across_buckets():
    """closing_balance is the whole-account total, duplicated across the
    12 bucket rows for any given date."""
    loader = _basic_loader(20)
    panel = aggregate_daily_panel(loader, user_id="u1")

    for date_value, group in panel.groupby("date"):
        unique_balances = group["closing_balance"].unique()
        assert len(unique_balances) == 1, f"closing_balance differs across buckets for {date_value}: {unique_balances}"


def test_unused_buckets_are_zero_filled():
    loader = _basic_loader(20)
    panel = aggregate_daily_panel(loader, user_id="u1")

    # The synthetic data only writes to 'groceries' and 'salary'. All
    # other buckets must have bucket_total == 0 throughout.
    used_buckets = {"groceries", "salary"}
    for bucket in CATEGORY_BUCKETS:
        rows = panel[panel["category_bucket"] == bucket]
        if bucket in used_buckets:
            assert rows["bucket_total"].abs().sum() > 0
        else:
            assert (rows["bucket_total"] == 0.0).all()


def test_scheduled_event_amount_zero_filled_when_no_scheduler():
    loader = _basic_loader(20)
    panel = aggregate_daily_panel(loader, user_id="u1", scheduled_df=None)
    assert (panel["scheduled_event_amount"] == 0.0).all()


def test_scheduled_event_amount_joins_per_bucket():
    loader = _basic_loader(60)
    rule = RecurrenceRule(
        merchant="landlord",
        amount=25_000,
        category_bucket="rent",
        rrule_freq="monthly",
        day_of_month=5,
        day_of_week=None,
        next_occurrence=date(2026, 1, 5),
        end_date=None,
        confidence=1.0,
        source="heuristic",
    )
    scheduled_df = project_scheduled_cashflows([rule], date(2026, 1, 1), date(2026, 3, 1))
    panel = aggregate_daily_panel(loader, scheduled_df=scheduled_df, user_id="u1")

    # On Jan 5, rent bucket carries the projected amount; the other
    # eleven buckets carry 0.
    jan_5 = panel[panel["date"] == pd.Timestamp("2026-01-05")]
    rent_row = jan_5[jan_5["category_bucket"] == "rent"]
    assert rent_row["scheduled_event_amount"].iloc[0] == -25_000.0
    other_rows = jan_5[jan_5["category_bucket"] != "rent"]
    assert (other_rows["scheduled_event_amount"] == 0.0).all()

    # Off-event dates carry 0 across all buckets.
    jan_3 = panel[panel["date"] == pd.Timestamp("2026-01-03")]
    assert (jan_3["scheduled_event_amount"] == 0.0).all()


def test_panel_time_idx_is_per_bucket_monotonic():
    loader = _basic_loader(15)
    panel = aggregate_daily_panel(loader, user_id="u1")
    for _, group in panel.groupby("category_bucket"):
        sorted_group = group.sort_values("date")
        assert sorted_group["time_idx"].is_monotonic_increasing
        assert sorted_group["time_idx"].iloc[0] == 0


def test_panel_creates_timeseries_dataset_with_panel_groups():
    """RFC-005 §3 — group_ids=[user_id, category_bucket]."""
    loader = _basic_loader(80)
    panel = aggregate_daily_panel(loader, user_id="u1")

    ts_dataset = create_timeseries_dataset(panel, max_encoder_length=30, max_prediction_length=7)

    assert ts_dataset.target == "closing_balance"
    assert ts_dataset.group_ids == ["user_id", "category_bucket"]
    assert "scheduled_event_amount" in ts_dataset.time_varying_known_reals
    assert "category_bucket" in ts_dataset.static_categoricals
    assert "user_id" in ts_dataset.static_categoricals


def test_panel_no_data_returns_empty_panel_with_schema():
    loader = TransactionLoader(pd.DataFrame({"date": [], "amount": []}))
    panel = aggregate_daily_panel(loader, user_id="u1")
    assert panel.empty
    for col in (
        "date",
        "user_id",
        "category_bucket",
        "bucket_total",
        "closing_balance",
        "scheduled_event_amount",
    ):
        assert col in panel.columns
