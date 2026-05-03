"""Tests for RFC-005 Layer 1 — heuristic recurrence detector + projection."""

from __future__ import annotations

from datetime import date

import pandas as pd

from packages.forecasting.scheduler import (
    CATEGORY_BUCKETS,
    RecurrenceRule,
    detect_recurring_cashflows,
    project_scheduled_cashflows,
)


def _build_monthly_pattern(merchant: str, amount: float, day_of_month: int, months: int = 4):
    """Build raw transactions with one occurrence per month on ``day_of_month``."""
    rows = []
    base = date(2025, 1, 1)
    for m in range(months):
        rows.append(
            {
                "date": pd.Timestamp(base.replace(month=m + 1, day=day_of_month)),
                "amount": amount,
                "merchant": merchant,
            }
        )
    return pd.DataFrame(rows)


def test_detects_monthly_salary_inflow():
    df = _build_monthly_pattern("Acme Payroll", 50_000, day_of_month=1, months=4)
    df["category"] = "Salary"

    rules = detect_recurring_cashflows(df, today=date(2025, 5, 15))

    assert len(rules) == 1
    rule = rules[0]
    assert rule.rrule_freq == "monthly"
    assert rule.day_of_month == 1
    assert rule.merchant == "acme payroll"
    assert rule.category_bucket == "salary"
    assert rule.amount == 50_000
    assert rule.source == "heuristic"
    assert 0.0 < rule.confidence <= 1.0


def test_detects_monthly_rent_outflow():
    df = _build_monthly_pattern("Best Landlord", -25_000, day_of_month=5, months=5)
    df["category"] = "Rent & Mortgage"

    rules = detect_recurring_cashflows(df, today=date(2025, 6, 10))

    assert len(rules) == 1
    rule = rules[0]
    assert rule.category_bucket == "rent"
    assert rule.day_of_month == 5
    assert rule.amount == 25_000  # stored as positive magnitude


def test_detects_monthly_subscription_with_amount_tolerance():
    """A subscription whose amount drifts ±5% across renewals is still
    detected as one rule."""
    rows = [
        {"date": pd.Timestamp("2025-01-15"), "amount": -1490.0, "merchant": "Netflix"},
        {"date": pd.Timestamp("2025-02-15"), "amount": -1499.0, "merchant": "Netflix"},
        {"date": pd.Timestamp("2025-03-15"), "amount": -1510.0, "merchant": "Netflix"},
        {"date": pd.Timestamp("2025-04-15"), "amount": -1499.0, "merchant": "Netflix"},
    ]
    df = pd.DataFrame(rows)
    df["category"] = "Subscriptions"

    rules = detect_recurring_cashflows(df, today=date(2025, 5, 1))

    assert len(rules) == 1
    rule = rules[0]
    assert rule.rrule_freq == "monthly"
    assert rule.day_of_month == 15
    assert rule.category_bucket == "entertainment"


def test_skips_pattern_below_min_occurrences():
    """Two occurrences alone are not enough to declare a rule."""
    df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2025-01-01"), pd.Timestamp("2025-02-01")],
            "amount": [-1000.0, -1000.0],
            "merchant": ["RareMerchant", "RareMerchant"],
        }
    )
    rules = detect_recurring_cashflows(df, today=date(2025, 5, 1))
    assert rules == []


def test_handles_empty_dataframe():
    assert detect_recurring_cashflows(pd.DataFrame()) == []


def test_recurrence_rule_validates_inputs():
    """The dataclass rejects unknown buckets / freq / source."""
    import pytest

    with pytest.raises(ValueError):
        RecurrenceRule(
            merchant="x",
            amount=10.0,
            category_bucket="not_a_bucket",
            rrule_freq="monthly",
            day_of_month=1,
            day_of_week=None,
            next_occurrence=date(2025, 1, 1),
            end_date=None,
            confidence=0.5,
            source="heuristic",
        )

    with pytest.raises(ValueError):
        RecurrenceRule(
            merchant="x",
            amount=10.0,
            category_bucket="rent",
            rrule_freq="weird",
            day_of_month=1,
            day_of_week=None,
            next_occurrence=date(2025, 1, 1),
            end_date=None,
            confidence=0.5,
            source="heuristic",
        )


def test_project_monthly_rule_emits_correct_days():
    rule = RecurrenceRule(
        merchant="Acme",
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

    df = project_scheduled_cashflows([rule], date(2026, 1, 1), date(2026, 4, 30))

    # Expect 4 occurrences: Jan 5, Feb 5, Mar 5, Apr 5
    assert len(df) == 4
    assert sorted(d.date() for d in df["date"]) == [
        date(2026, 1, 5),
        date(2026, 2, 5),
        date(2026, 3, 5),
        date(2026, 4, 5),
    ]
    # Outflow → negative scheduled_amount
    assert (df["scheduled_amount"] == -25_000).all()
    assert (df["category_bucket"] == "rent").all()


def test_project_salary_rule_signs_positive():
    rule = RecurrenceRule(
        merchant="Payroll",
        amount=50_000,
        category_bucket="salary",
        rrule_freq="monthly",
        day_of_month=1,
        day_of_week=None,
        next_occurrence=date(2026, 1, 1),
        end_date=None,
        confidence=1.0,
        source="heuristic",
    )

    df = project_scheduled_cashflows([rule], date(2026, 1, 1), date(2026, 3, 31))

    assert (df["scheduled_amount"] == 50_000).all()


def test_project_weekly_rule_emits_weekly_cadence():
    # Tuesday = 1
    rule = RecurrenceRule(
        merchant="Gym",
        amount=300,
        category_bucket="health",
        rrule_freq="weekly",
        day_of_month=None,
        day_of_week=1,
        next_occurrence=date(2026, 1, 6),
        end_date=None,
        confidence=1.0,
        source="heuristic",
    )

    df = project_scheduled_cashflows([rule], date(2026, 1, 1), date(2026, 1, 31))

    # Tuesdays in Jan 2026: 6, 13, 20, 27 → 4 occurrences
    assert len(df) == 4
    assert sorted(d.date() for d in df["date"]) == [
        date(2026, 1, 6),
        date(2026, 1, 13),
        date(2026, 1, 20),
        date(2026, 1, 27),
    ]


def test_project_returns_empty_with_no_rules():
    df = project_scheduled_cashflows([], date(2026, 1, 1), date(2026, 1, 31))
    assert df.empty
    # Schema still present so downstream joins do not break.
    assert {"date", "category_bucket", "scheduled_amount"}.issubset(df.columns)


def test_category_buckets_constant_size():
    assert len(CATEGORY_BUCKETS) == 12
