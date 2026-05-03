"""RFC-005 Layer 1 — heuristic recurrence detector + projection.

No ML. Pattern matching only. ``source='heuristic'`` rules come from this
module; ``source='user_override'`` and ``source='intent'`` (LLD 010) write
to the same ``public.scheduled_cashflows`` table from elsewhere.

Detection rules (per RFC-005):
    - Same merchant (case-normalised) — required.
    - Same absolute amount within ±5% tolerance.
    - Same day-of-month within ±2 days (monthly freq) OR same day-of-week
      (weekly).
    - At least 3 matching occurrences across distinct months.
    - Confidence = matched_occurrences / expected_occurrences in [0, 1].

Projection: a list of ``RecurrenceRule`` is expanded into a long-format
DataFrame of (date, category_bucket, scheduled_amount) rows across the
forecast horizon. Sign convention: + for income buckets (salary),
- for spend buckets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Iterable

import pandas as pd

from packages.forecasting.buckets import CATEGORY_BUCKETS, INCOME_BUCKETS
from packages.forecasting.category_mapping import map_classifier_label_to_bucket

__all__ = [
    "CATEGORY_BUCKETS",
    "RecurrenceRule",
    "detect_recurring_cashflows",
    "project_scheduled_cashflows",
]


@dataclass
class RecurrenceRule:
    """One detected recurring cashflow rule.

    ``amount`` is stored as the positive magnitude observed in
    transactions; sign is applied at projection time based on whether
    the bucket is an income bucket.
    """

    merchant: str | None
    amount: float
    category_bucket: str
    rrule_freq: str  # 'monthly' | 'weekly' | 'biweekly' | 'quarterly' | 'annual'
    day_of_month: int | None
    day_of_week: int | None
    next_occurrence: date
    end_date: date | None
    confidence: float  # in [0, 1]
    source: str  # 'heuristic' | 'user_override' | 'intent'

    def __post_init__(self) -> None:
        if self.category_bucket not in CATEGORY_BUCKETS:
            raise ValueError(f"category_bucket {self.category_bucket!r} not in CATEGORY_BUCKETS")
        if self.rrule_freq not in {"monthly", "weekly", "biweekly", "quarterly", "annual"}:
            raise ValueError(f"rrule_freq {self.rrule_freq!r} invalid")
        if self.source not in {"heuristic", "user_override", "intent"}:
            raise ValueError(f"source {self.source!r} invalid")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence {self.confidence} not in [0,1]")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def _normalise_merchant(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip().lower()
    return s or None


def _resolve_bucket(category_value: object) -> str:
    if category_value is None:
        return "other"
    return map_classifier_label_to_bucket(str(category_value))


def detect_recurring_cashflows(
    txns: pd.DataFrame,
    *,
    amount_tolerance_pct: float = 0.05,
    dom_tolerance_days: int = 2,
    min_occurrences: int = 3,
    today: date | None = None,
) -> list[RecurrenceRule]:
    """Scan transactions for recurring monthly / weekly patterns.

    Args:
        txns: Raw transactions with at minimum a ``date`` and ``amount``
            column. Optional ``merchant`` / ``merchant_name`` and
            ``category`` columns are used when present.
        amount_tolerance_pct: Fractional spread allowed within a group
            (default 5%).
        dom_tolerance_days: Day-of-month spread allowed for monthly
            patterns (default 2 days).
        min_occurrences: Minimum count of matching transactions to
            qualify as a rule (default 3).
        today: Reference date for ``next_occurrence`` projection. Defaults
            to ``date.today()``. Pass-in is for deterministic testing.

    Returns:
        A list of detected ``RecurrenceRule``. Empty when no patterns
        meet the threshold.
    """
    if txns is None or len(txns) == 0:
        return []

    today = today or date.today()
    df = txns.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    df = df[df["amount"] != 0.0]

    if df.empty:
        return []

    # Merchant is the primary group key; tests pass either ``merchant`` or
    # ``merchant_name`` (the latter matches the trainer projection).
    merchant_col: str | None = None
    for candidate in ("merchant", "merchant_name"):
        if candidate in df.columns:
            merchant_col = candidate
            break
    if merchant_col is None:
        df["merchant"] = None
        merchant_col = "merchant"

    df["_merchant_norm"] = df[merchant_col].map(_normalise_merchant)
    df["_abs_amount"] = df["amount"].abs()
    df["_sign"] = df["amount"].apply(lambda a: 1 if a > 0 else -1)
    df["_dom"] = df["date"].dt.day
    df["_dow"] = df["date"].dt.dayofweek
    df["_year_month"] = df["date"].dt.to_period("M").astype(str)

    if "category" in df.columns:
        df["_bucket"] = df["category"].map(_resolve_bucket)
    else:
        df["_bucket"] = "other"

    rules: list[RecurrenceRule] = []

    # Group by (merchant_norm, sign). Within each merchant we then bucket
    # by approximate amount (rounded to a tolerance bin).
    for (merchant_norm, sign), group in df.groupby(["_merchant_norm", "_sign"], dropna=False):
        if merchant_norm is None or len(group) < min_occurrences:
            continue

        # Bin amounts. Two transactions whose amounts are within
        # ``amount_tolerance_pct`` of each other are considered the same.
        sorted_g = group.sort_values("_abs_amount").copy()
        bins: list[list[int]] = []  # each inner list is row indices
        for idx, row in sorted_g.iterrows():
            placed = False
            for b in bins:
                ref_amount = sorted_g.loc[b[0], "_abs_amount"]
                if abs(row["_abs_amount"] - ref_amount) <= ref_amount * amount_tolerance_pct:
                    b.append(idx)
                    placed = True
                    break
            if not placed:
                bins.append([idx])

        for bin_indices in bins:
            sub = sorted_g.loc[bin_indices].sort_values("date")
            if len(sub) < min_occurrences:
                continue

            # Try monthly first.
            monthly_rule = _try_monthly(
                sub,
                sign=int(sign),
                dom_tolerance_days=dom_tolerance_days,
                min_occurrences=min_occurrences,
                today=today,
            )
            if monthly_rule is not None:
                rules.append(monthly_rule)
                continue

            # Then weekly.
            weekly_rule = _try_weekly(
                sub,
                sign=int(sign),
                min_occurrences=min_occurrences,
                today=today,
            )
            if weekly_rule is not None:
                rules.append(weekly_rule)

    return rules


def _dominant_bucket(sub: pd.DataFrame, sign: int) -> str:
    """Pick the most-frequent category bucket in the group; signed sign
    is used as a final fallback (positive → salary, negative → other)."""
    counts = sub["_bucket"].value_counts()
    if not counts.empty:
        bucket = str(counts.index[0])
        if bucket in CATEGORY_BUCKETS:
            return bucket
    return "salary" if sign > 0 else "other"


def _try_monthly(
    sub: pd.DataFrame,
    *,
    sign: int,
    dom_tolerance_days: int,
    min_occurrences: int,
    today: date,
) -> RecurrenceRule | None:
    months = sub["_year_month"].nunique()
    if months < min_occurrences:
        return None

    median_dom = int(sub["_dom"].median())
    within_tolerance = (sub["_dom"] - median_dom).abs() <= dom_tolerance_days
    matching = sub[within_tolerance]
    matching_months = matching["_year_month"].nunique()
    if matching_months < min_occurrences:
        return None

    first_date = pd.Timestamp(matching["date"].min()).date()
    last_date = pd.Timestamp(matching["date"].max()).date()
    span_months = max(
        1,
        (last_date.year - first_date.year) * 12 + (last_date.month - first_date.month) + 1,
    )
    confidence = min(1.0, matching_months / span_months)

    bucket = _dominant_bucket(sub, sign)
    median_amount = float(matching["_abs_amount"].median())
    merchant = sub.iloc[0]["_merchant_norm"]

    return RecurrenceRule(
        merchant=merchant,
        amount=median_amount,
        category_bucket=bucket,
        rrule_freq="monthly",
        day_of_month=median_dom,
        day_of_week=None,
        next_occurrence=_next_monthly_occurrence(median_dom, today),
        end_date=None,
        confidence=confidence,
        source="heuristic",
    )


def _try_weekly(
    sub: pd.DataFrame,
    *,
    sign: int,
    min_occurrences: int,
    today: date,
) -> RecurrenceRule | None:
    dow_counts = sub["_dow"].value_counts()
    if dow_counts.empty:
        return None
    top_dow = int(dow_counts.index[0])
    matching = sub[sub["_dow"] == top_dow]
    if len(matching) < min_occurrences:
        return None

    weeks_observed = matching["date"].dt.isocalendar().week.nunique()
    if weeks_observed < min_occurrences:
        return None

    first_date = pd.Timestamp(matching["date"].min()).date()
    last_date = pd.Timestamp(matching["date"].max()).date()
    span_weeks = max(1, ((last_date - first_date).days // 7) + 1)
    confidence = min(1.0, weeks_observed / span_weeks)

    bucket = _dominant_bucket(sub, sign)
    median_amount = float(matching["_abs_amount"].median())
    merchant = sub.iloc[0]["_merchant_norm"]

    return RecurrenceRule(
        merchant=merchant,
        amount=median_amount,
        category_bucket=bucket,
        rrule_freq="weekly",
        day_of_month=None,
        day_of_week=top_dow,
        next_occurrence=_next_weekly_occurrence(top_dow, today),
        end_date=None,
        confidence=confidence,
        source="heuristic",
    )


def _next_monthly_occurrence(day_of_month: int, today: date) -> date:
    """Return the next occurrence of ``day_of_month`` on or after ``today``."""
    candidate_year = today.year
    candidate_month = today.month
    while True:
        try:
            candidate = date(candidate_year, candidate_month, day_of_month)
        except ValueError:
            # day_of_month invalid for this month (e.g. Feb 30); fall to next month.
            candidate_month += 1
            if candidate_month > 12:
                candidate_year += 1
                candidate_month = 1
            continue
        if candidate >= today:
            return candidate
        candidate_month += 1
        if candidate_month > 12:
            candidate_year += 1
            candidate_month = 1


def _next_weekly_occurrence(day_of_week: int, today: date) -> date:
    """Return the next occurrence of ``day_of_week`` (Mon=0..Sun=6) on
    or after ``today``."""
    delta = (day_of_week - today.weekday()) % 7
    return today + timedelta(days=delta)


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


_FREQ_DELTAS = {
    "weekly": timedelta(days=7),
    "biweekly": timedelta(days=14),
}


def project_scheduled_cashflows(
    rules: Iterable[RecurrenceRule],
    horizon_start: date,
    horizon_end: date,
) -> pd.DataFrame:
    """Expand active rules into per-day scheduled events across the horizon.

    Output columns:
        date              date (datetime64[ns] in pandas)
        category_bucket   str (one of CATEGORY_BUCKETS)
        scheduled_amount  float (signed; +amount for income buckets,
                                 -amount for spend buckets)
        merchant          str | None
        source            str
        confidence        float

    Multiple rules can overlap on the same (date, bucket) — the caller
    sums them on join into the panel.
    """
    if horizon_end < horizon_start:
        raise ValueError(f"horizon_end ({horizon_end}) must be >= horizon_start ({horizon_start})")

    rows: list[dict] = []
    for rule in rules:
        signed = rule.amount if rule.category_bucket in INCOME_BUCKETS else -rule.amount
        for occurrence in _iter_occurrences(rule, horizon_start, horizon_end):
            rows.append(
                {
                    "date": pd.Timestamp(occurrence),
                    "category_bucket": rule.category_bucket,
                    "scheduled_amount": float(signed),
                    "merchant": rule.merchant,
                    "source": rule.source,
                    "confidence": float(rule.confidence),
                }
            )

    if not rows:
        return pd.DataFrame(
            {
                "date": pd.Series(dtype="datetime64[ns]"),
                "category_bucket": pd.Series(dtype="object"),
                "scheduled_amount": pd.Series(dtype="float64"),
                "merchant": pd.Series(dtype="object"),
                "source": pd.Series(dtype="object"),
                "confidence": pd.Series(dtype="float64"),
            }
        )
    return pd.DataFrame(rows)


def _iter_occurrences(
    rule: RecurrenceRule,
    horizon_start: date,
    horizon_end: date,
) -> Iterable[date]:
    end = rule.end_date or horizon_end
    end = min(end, horizon_end)

    if rule.rrule_freq == "monthly":
        if rule.day_of_month is None:
            return
        cursor_year, cursor_month = horizon_start.year, horizon_start.month
        while True:
            try:
                candidate = date(cursor_year, cursor_month, rule.day_of_month)
            except ValueError:
                cursor_month += 1
                if cursor_month > 12:
                    cursor_year += 1
                    cursor_month = 1
                continue
            if candidate > end:
                return
            if candidate >= horizon_start:
                yield candidate
            cursor_month += 1
            if cursor_month > 12:
                cursor_year += 1
                cursor_month = 1
    elif rule.rrule_freq == "quarterly":
        if rule.day_of_month is None:
            return
        cursor_year, cursor_month = horizon_start.year, horizon_start.month
        while True:
            try:
                candidate = date(cursor_year, cursor_month, rule.day_of_month)
            except ValueError:
                cursor_month += 3
                while cursor_month > 12:
                    cursor_year += 1
                    cursor_month -= 12
                continue
            if candidate > end:
                return
            if candidate >= horizon_start:
                yield candidate
            cursor_month += 3
            while cursor_month > 12:
                cursor_year += 1
                cursor_month -= 12
    elif rule.rrule_freq == "annual":
        if rule.day_of_month is None:
            return
        cursor_year = horizon_start.year
        # Use rule.next_occurrence's month as the anchor.
        anchor_month = rule.next_occurrence.month
        while True:
            try:
                candidate = date(cursor_year, anchor_month, rule.day_of_month)
            except ValueError:
                cursor_year += 1
                continue
            if candidate > end:
                return
            if candidate >= horizon_start:
                yield candidate
            cursor_year += 1
    elif rule.rrule_freq in _FREQ_DELTAS:
        if rule.day_of_week is None:
            return
        delta = _FREQ_DELTAS[rule.rrule_freq]
        # Anchor: first matching weekday on or after horizon_start.
        offset = (rule.day_of_week - horizon_start.weekday()) % 7
        cursor = horizon_start + timedelta(days=offset)
        while cursor <= end:
            yield cursor
            cursor = cursor + delta
