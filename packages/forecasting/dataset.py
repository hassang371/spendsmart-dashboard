"""RFC-005 Layer 2 — category-level daily panel aggregation.

The panel emits one row per (date, category_bucket) pair. The TFT
``TimeSeriesDataSet`` consumes the panel with
``group_ids=["user_id", "category_bucket"]``.

Backwards compatibility: ``prepare_training_data`` is preserved as the
public entrypoint and now returns panel output (12 buckets × N days
per user). All downstream callers (``trainer.run_training``,
``inference.predict_with_tft``, ``apps/worker/main.py``) consume the
panel shape via ``create_timeseries_dataset``.
"""

from __future__ import annotations

from datetime import date as date_type

import numpy as np
import pandas as pd
from pytorch_forecasting import TimeSeriesDataSet
from sklearn.preprocessing import RobustScaler

from packages.forecasting.buckets import CATEGORY_BUCKETS, INCOME_BUCKETS
from packages.forecasting.category_mapping import map_classifier_label_to_bucket


class TimeScalar:
    def __init__(self, column="amount", quantile_range=(25.0, 75.0)):
        """RobustScaler wrapper for a specific column.

        Scales data using statistics that are robust to outliers.
        """
        self.column = column
        self.scaler = RobustScaler(quantile_range=quantile_range)

    def fit(self, df: pd.DataFrame):
        if self.column not in df.columns:
            raise KeyError(f"Column '{self.column}' not found in DataFrame")
        data = df[[self.column]].values
        self.scaler.fit(data)
        return self

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column not in df.columns:
            raise KeyError(f"Column '{self.column}' not found in DataFrame")
        df_scaled = df.copy()
        data = df[[self.column]].values
        scaled_values = self.scaler.transform(data)
        df_scaled[self.column] = scaled_values.flatten()
        return df_scaled

    def inverse_transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if self.column not in df.columns:
            raise KeyError(f"Column '{self.column}' not found in DataFrame")
        df_inv = df.copy()
        data = df[[self.column]].values
        inv_values = self.scaler.inverse_transform(data)
        df_inv[self.column] = inv_values.flatten()
        return df_inv


class TransactionLoader:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        if "date" in self.df.columns:
            self.df["date"] = pd.to_datetime(self.df["date"])

    def aggregate_daily(self, start_date=None, end_date=None) -> pd.DataFrame:
        """Aggregates transactions into daily summaries (single-series).

        Returns DataFrame with index 'date' and columns:
        - daily_spend: positive float (sum of absolute negative transactions)
        - daily_income: positive float (sum of positive transactions)
        - closing_balance: cumulative sum of (income - spend)

        This single-series view is retained for callers that need a
        whole-account total (e.g. evaluation harness, CSV exports). The
        panel-aware training path uses :func:`aggregate_daily_panel`.
        """
        df = self.df.copy()

        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        df.set_index("date", inplace=True)

        income_series = df[df["amount"] > 0]["amount"].resample("D").sum()
        spend_series = df[df["amount"] < 0]["amount"].resample("D").sum().abs()

        daily_df = pd.DataFrame({"daily_income": income_series, "daily_spend": spend_series})
        daily_df.fillna(0.0, inplace=True)

        if start_date and end_date:
            idx = pd.date_range(start_date, end_date)
            daily_df = daily_df.reindex(idx, fill_value=0.0)

        daily_df["net_change"] = daily_df["daily_income"] - daily_df["daily_spend"]
        daily_df["closing_balance"] = daily_df["net_change"].cumsum()
        daily_df.drop(columns=["net_change"], inplace=True)
        daily_df.index.name = "date"
        return daily_df

    def enrich_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Adds derived time features needed for TFT (legacy single-series).

        Retained for tests and tooling that still consume the
        single-series shape; the panel pipeline computes these features
        inside :func:`aggregate_daily_panel`.
        """
        df = df.copy()
        if df.index.name == "date":
            df.reset_index(inplace=True)
        df.sort_values("date", inplace=True)
        df["time_idx"] = np.arange(len(df))
        df["day_of_week"] = df["date"].dt.dayofweek.astype(str).astype("category")
        df["day_of_month"] = df["date"].dt.day.astype(str).astype("category")
        df["group_id"] = "main_user"
        return df


# ---------------------------------------------------------------------------
# RFC-005 — category-level panel
# ---------------------------------------------------------------------------


def aggregate_daily_panel(
    loader: TransactionLoader,
    scheduled_df: pd.DataFrame | None = None,
    *,
    user_id: str = "main_user",
    start_date: object = None,
    end_date: object = None,
) -> pd.DataFrame:
    """Long-format panel: one row per (date, category_bucket) pair.

    Output columns:
        date                   datetime64[ns]
        user_id                str (constant per panel call)
        category_bucket        str (one of CATEGORY_BUCKETS, dense)
        bucket_total           float (signed; + income, - spend)
        daily_income           float (whole-day income, duplicated across buckets)
        daily_spend            float (whole-day spend, duplicated across buckets)
        closing_balance        float (whole-account closing balance, duplicated)
        scheduled_event_amount float (per-(date, bucket); zero if no event)
        is_payday              category '0' | '1'
        day_of_week            category
        day_of_month           category
        month                  category
        time_idx               int monotonic per (date, bucket)
        group_id               str (= user_id, retained for legacy tests)

    Args:
        loader: ``TransactionLoader`` over the user's raw transactions.
        scheduled_df: Optional output of
            :func:`packages.forecasting.scheduler.project_scheduled_cashflows`.
            When provided, joined into the panel as
            ``scheduled_event_amount``. When ``None`` or empty, the
            column is zero-filled.
        user_id: Identifier written into the panel's ``user_id`` column.
        start_date / end_date: Optional date filters passed to the
            single-series aggregator and used to densify the panel.

    Behaviour:
        - The panel is dense: every (date, bucket) cell exists, even for
          buckets the user has never used. Missing cells are zero-filled
          (TFT requires a dense series per group_id).
        - ``closing_balance`` is the whole-account cumulative balance and
          is duplicated across the 12 bucket rows for any given date —
          the pytorch-forecasting panel convention (target attached to
          each group's series).
        - ``scheduled_event_amount`` is per-(date, bucket): on a date
          where Layer 1 projects a rent event, only the ``rent`` row
          carries the amount; the other 11 rows carry 0.
    """
    df = loader.df.copy()
    if start_date:
        df = df[df["date"] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df["date"] <= pd.to_datetime(end_date)]

    if df.empty:
        # Build an empty-but-dense panel over the requested range when
        # provided; otherwise return an empty frame with the correct schema.
        if start_date and end_date:
            dates = pd.date_range(start_date, end_date, freq="D")
        else:
            return _empty_panel(user_id)
        return _build_dense_panel(
            dates=pd.to_datetime(dates),
            per_day_per_bucket=pd.DataFrame({"date": [], "category_bucket": [], "bucket_total": []}),
            scheduled_df=scheduled_df,
            user_id=user_id,
        )

    # --- per-transaction → bucket assignment --------------------------------
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    if "category" in df.columns:
        df["category_bucket"] = df["category"].apply(
            lambda v: map_classifier_label_to_bucket(v) if pd.notna(v) else _bucket_from_sign(0)
        )
    else:
        df["category_bucket"] = "other"

    # Override: for inflows to non-income buckets, route to "salary" bucket
    # only when no category info was available. With explicit category we
    # honour the classifier mapping. Net effect: positive amounts with no
    # category fall into "salary"; negative amounts with no category fall
    # into "other".
    no_cat_mask = ("category" not in loader.df.columns) | df.get("category", pd.Series(index=df.index)).isna()
    if isinstance(no_cat_mask, pd.Series):
        positive_no_cat = no_cat_mask & (df["amount"] > 0)
        df.loc[positive_no_cat, "category_bucket"] = "salary"

    # --- aggregate per (date, bucket) --------------------------------------
    # Strip timezone so downstream merges with scheduled_df (tz-naive,
    # produced by project_scheduled_cashflows from python `date` objects)
    # don't crash on dtype mismatch (datetime64[ns, UTC] vs datetime64[ns]).
    _dates = pd.to_datetime(df["date"])
    if getattr(_dates.dt, "tz", None) is not None:
        _dates = _dates.dt.tz_convert("UTC").dt.tz_localize(None)
    df["_date"] = _dates.dt.normalize()
    grouped = (
        df.groupby(["_date", "category_bucket"])["amount"]
        .sum()
        .reset_index()
        .rename(columns={"_date": "date", "amount": "bucket_total"})
    )

    # --- build dense date range --------------------------------------------
    if start_date and end_date:
        dates = pd.date_range(start_date, end_date, freq="D")
    else:
        dates = pd.date_range(df["_date"].min(), df["_date"].max(), freq="D")

    return _build_dense_panel(
        dates=pd.to_datetime(dates),
        per_day_per_bucket=grouped,
        scheduled_df=scheduled_df,
        user_id=user_id,
    )


def _bucket_from_sign(amount: float) -> str:
    return "salary" if amount > 0 else "other"


def _empty_panel(user_id: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.Series(dtype="datetime64[ns]"),
            "user_id": pd.Series(dtype="object"),
            "category_bucket": pd.Series(dtype="object"),
            "bucket_total": pd.Series(dtype="float64"),
            "daily_income": pd.Series(dtype="float64"),
            "daily_spend": pd.Series(dtype="float64"),
            "closing_balance": pd.Series(dtype="float64"),
            "scheduled_event_amount": pd.Series(dtype="float64"),
            "is_payday": pd.Series(dtype="category"),
            "day_of_week": pd.Series(dtype="category"),
            "day_of_month": pd.Series(dtype="category"),
            "month": pd.Series(dtype="category"),
            "time_idx": pd.Series(dtype="int64"),
            "group_id": pd.Series(dtype="object"),
        }
    )


def _build_dense_panel(
    *,
    dates: pd.DatetimeIndex,
    per_day_per_bucket: pd.DataFrame,
    scheduled_df: pd.DataFrame | None,
    user_id: str,
) -> pd.DataFrame:
    """Cross-join (dates × buckets), zero-fill, attach scalars + scheduled."""
    bucket_index = pd.MultiIndex.from_product([dates, list(CATEGORY_BUCKETS)], names=["date", "category_bucket"])
    panel = pd.DataFrame(index=bucket_index).reset_index()

    if not per_day_per_bucket.empty:
        per_day_per_bucket = per_day_per_bucket.copy()
        _d = pd.to_datetime(per_day_per_bucket["date"])
        if getattr(_d.dt, "tz", None) is not None:
            _d = _d.dt.tz_convert("UTC").dt.tz_localize(None)
        per_day_per_bucket["date"] = _d
        panel = panel.merge(per_day_per_bucket, on=["date", "category_bucket"], how="left")
    else:
        panel["bucket_total"] = 0.0
    panel["bucket_total"] = panel["bucket_total"].fillna(0.0).astype(float)

    # daily_income / daily_spend / closing_balance — derived from per-bucket
    # totals so the legacy single-series invariants are preserved.
    bucket_totals_by_date = panel.groupby("date")["bucket_total"].agg(
        daily_income=lambda s: float(s[s > 0].sum()),
        daily_spend=lambda s: float(-s[s < 0].sum()),
    )
    bucket_totals_by_date["net_change"] = bucket_totals_by_date["daily_income"] - bucket_totals_by_date["daily_spend"]
    bucket_totals_by_date["closing_balance"] = bucket_totals_by_date["net_change"].cumsum()
    bucket_totals_by_date = bucket_totals_by_date[["daily_income", "daily_spend", "closing_balance"]].reset_index()
    panel = panel.merge(bucket_totals_by_date, on="date", how="left")

    # scheduled_event_amount join
    if scheduled_df is not None and not scheduled_df.empty:
        sched = scheduled_df.copy()
        _sd = pd.to_datetime(sched["date"])
        if getattr(_sd.dt, "tz", None) is not None:
            _sd = _sd.dt.tz_convert("UTC").dt.tz_localize(None)
        sched["date"] = _sd
        sched = (
            sched.groupby(["date", "category_bucket"])["scheduled_amount"]
            .sum()
            .reset_index()
            .rename(columns={"scheduled_amount": "scheduled_event_amount"})
        )
        panel = panel.merge(sched, on=["date", "category_bucket"], how="left")
    else:
        panel["scheduled_event_amount"] = 0.0
    panel["scheduled_event_amount"] = panel["scheduled_event_amount"].fillna(0.0).astype(float)

    panel["user_id"] = user_id
    panel["group_id"] = user_id  # legacy alias for back-compat tools

    # is_payday derived from daily_income peaks (legacy parity).
    panel["is_payday"] = _detect_panel_paydays(panel)

    panel["day_of_week"] = panel["date"].dt.dayofweek.astype(str).astype("category")
    panel["day_of_month"] = panel["date"].dt.day.astype(str).astype("category")
    panel["month"] = panel["date"].dt.month.astype(str).astype("category")
    panel["is_payday"] = panel["is_payday"].astype(str).astype("category")

    # time_idx: monotonic per group (one row per date within a bucket).
    panel = panel.sort_values(["category_bucket", "date"]).reset_index(drop=True)
    panel["time_idx"] = panel.groupby("category_bucket").cumcount().astype("int64")

    # Final column order — predictable for downstream consumers.
    return panel[
        [
            "date",
            "user_id",
            "category_bucket",
            "bucket_total",
            "daily_income",
            "daily_spend",
            "closing_balance",
            "scheduled_event_amount",
            "is_payday",
            "day_of_week",
            "day_of_month",
            "month",
            "time_idx",
            "group_id",
        ]
    ]


def _detect_panel_paydays(panel: pd.DataFrame, threshold_percentile: float = 90) -> pd.Series:
    """Vectorised payday flag for the panel: a date is a payday iff its
    whole-day income exceeds the 90th-percentile of positive incomes AND
    the day-of-month repeats across at least 2 months.
    """
    if "daily_income" not in panel.columns:
        return pd.Series(0, index=panel.index)
    by_date = panel.drop_duplicates(subset=["date"])[["date", "daily_income"]].set_index("date").sort_index()
    positive = by_date["daily_income"][by_date["daily_income"] > 0]
    if positive.empty:
        return pd.Series(0, index=panel.index)
    threshold = positive.quantile(threshold_percentile / 100)
    large = by_date["daily_income"] >= threshold
    dom = by_date.index.day
    payday_doms: list[int] = []
    for day in dom[large].unique():
        if large[dom == day].sum() >= 2:
            payday_doms.append(day)
    is_payday_by_date = pd.Series(dom.isin(payday_doms).astype(int), index=by_date.index)
    return panel["date"].map(is_payday_by_date).fillna(0).astype(int)


# ---------------------------------------------------------------------------
# Legacy single-series helpers (retained for harness + tests)
# ---------------------------------------------------------------------------


def _detect_paydays(daily_df: pd.DataFrame, threshold_percentile: float = 90) -> pd.Series:
    """Detect payday pattern on a single-series daily DataFrame.

    Used by the legacy single-series tests. Panel uses
    :func:`_detect_panel_paydays`.
    """
    if "daily_income" not in daily_df.columns:
        return pd.Series(0, index=daily_df.index)

    income = daily_df["daily_income"]
    positive_income = income[income > 0]
    if positive_income.empty:
        return pd.Series(0, index=daily_df.index)

    threshold = positive_income.quantile(threshold_percentile / 100)
    large_deposit = income >= threshold

    if isinstance(daily_df.index, pd.DatetimeIndex):
        dom = daily_df.index.day
    elif "date" in daily_df.columns:
        dom = pd.to_datetime(daily_df["date"]).dt.day
    else:
        return large_deposit.astype(int)

    payday_days = []
    for day in dom[large_deposit].unique():
        if large_deposit[dom == day].sum() >= 2:
            payday_days.append(day)

    return pd.Series(dom.isin(payday_days).astype(int), index=daily_df.index)


# ---------------------------------------------------------------------------
# Public consolidation point
# ---------------------------------------------------------------------------


def prepare_training_data(
    transactions: pd.DataFrame,
    start_date=None,
    end_date=None,
    min_days: int = 0,
    *,
    user_id: str = "main_user",
    scheduled_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Canonical data preparation: aggregate → panel → enrich.

    Returns a long-format panel DataFrame with one row per
    (date, category_bucket). Per RFC-005, this is the input shape for
    the panel-aware ``create_timeseries_dataset``.

    Args:
        transactions: Raw transactions with at minimum ``date`` and
            ``amount`` columns. Optional columns:
                ``category``, ``merchant`` / ``merchant_name``.
        start_date / end_date: Optional date-range filters.
        min_days: Minimum required days of history. ``0`` (default)
            skips the check.
        user_id: ID written into the ``user_id`` group column.
        scheduled_df: Optional projection from
            :func:`packages.forecasting.scheduler.project_scheduled_cashflows`.

    Returns:
        Panel DataFrame ready for ``create_timeseries_dataset``.

    Raises:
        ValueError: When the panel has fewer distinct dates than
            ``min_days``.
    """
    loader = TransactionLoader(transactions)
    panel = aggregate_daily_panel(
        loader,
        scheduled_df=scheduled_df,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )

    distinct_days = panel["date"].nunique()
    if min_days > 0 and distinct_days < min_days:
        raise ValueError(
            f"Insufficient data: {distinct_days} days available, "
            f"but the model requires at least {min_days}. "
            f"Please upload more transaction history."
        )

    return panel


# ---------------------------------------------------------------------------
# TFT TimeSeriesDataSet construction (panel-aware)
# ---------------------------------------------------------------------------


def create_timeseries_dataset(
    data: pd.DataFrame,
    max_encoder_length: int = 30,
    max_prediction_length: int = 7,
) -> TimeSeriesDataSet:
    """Create a panel-aware ``TimeSeriesDataSet`` per RFC-005 §3.

    When ``data`` carries a ``category_bucket`` column, the dataset uses
    panel groups ``[user_id, category_bucket]``. When it does not (legacy
    single-series callers), the dataset falls back to the previous
    single-group ``[group_id]`` configuration. The fallback is
    transitional: Stage 5+ deletes single-series consumers.
    """
    if "category_bucket" in data.columns:
        known_categoricals = ["day_of_week", "day_of_month"]
        for optional in ("month", "is_payday"):
            if optional in data.columns:
                known_categoricals.append(optional)

        known_reals = ["time_idx"]
        if "scheduled_event_amount" in data.columns:
            known_reals.append("scheduled_event_amount")

        unknown_reals = ["closing_balance"]
        if "bucket_total" in data.columns:
            unknown_reals.append("bucket_total")

        return TimeSeriesDataSet(
            data,
            time_idx="time_idx",
            target="closing_balance",
            group_ids=["user_id", "category_bucket"],
            min_encoder_length=max_encoder_length // 2,
            max_encoder_length=max_encoder_length,
            min_prediction_length=1,
            max_prediction_length=max_prediction_length,
            static_categoricals=["user_id", "category_bucket"],
            time_varying_known_categoricals=known_categoricals,
            time_varying_known_reals=known_reals,
            time_varying_unknown_reals=unknown_reals,
            add_relative_time_idx=True,
            add_target_scales=True,
            add_encoder_length=True,
        )

    # Legacy single-series fallback.
    known_categoricals = ["day_of_week", "day_of_month"]
    if "is_payday" in data.columns:
        known_categoricals.append("is_payday")

    return TimeSeriesDataSet(
        data,
        time_idx="time_idx",
        target="closing_balance",
        group_ids=["group_id"],
        min_encoder_length=max_encoder_length // 2,
        max_encoder_length=max_encoder_length,
        min_prediction_length=1,
        max_prediction_length=max_prediction_length,
        static_categoricals=["group_id"],
        time_varying_known_categoricals=known_categoricals,
        time_varying_known_reals=["time_idx", "daily_income", "daily_spend"],
        time_varying_unknown_reals=["closing_balance"],
        add_relative_time_idx=True,
        add_target_scales=True,
        add_encoder_length=True,
    )
