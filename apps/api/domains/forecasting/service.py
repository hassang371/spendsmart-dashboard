"""Forecasting service — Stage 1 thin-delegation stub.

This is the minimal ForecastService skeleton produced in Stage 1
(LLD 009). It does basic tier routing + returns a legacy-shape
forecast dict so the router can thin-delegate to it without changing
the over-the-wire response. Stage 5 (RFC-003) replaces this with the
full ForecastResponse contract — insights, seven-quantile points,
prediction_id (uuid4), and atomic INSERT logging via the
``log_user_prediction`` RPC.

Stage 1 deliberately omits:
  - insights computation (Stage 5 owns ``compute_insights``)
  - prediction_id generation (Stage 5 owns uuid4 + RPC logging)
  - logger / metrics (Stage 5 / Stage 3 own those)
  - the RFC-003 seven-quantile point shape (Stage 5 swaps response_model)

TODO(Stage 2): swap the local placeholder dict shape for the
RFC-003 ``ForecastResponse`` Pydantic model once Stage 2 lands the
expanded ``schemas.py``.
TODO(Stage 5): wire insights + uuid4 prediction_id + RPC-based
``log_user_prediction`` call.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from packages.forecasting.dataset import TransactionLoader


class ForecastService:
    """Thin delegation target for the forecast router.

    The Supabase client is captured so Stage 5 can use it for the
    ``log_user_prediction`` RPC + variable-importance lookup without a
    further constructor change.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    def predict(
        self,
        df: pd.DataFrame,
        *,
        user_id: str,
        horizon: int = 7,
    ) -> dict[str, Any]:
        """Return a forecast for ``user_id`` over ``horizon`` days.

        Stage 1 stub: aggregates daily, computes a simple recent-30-day
        rolling average, and returns the legacy CSV-upload shape that
        the existing route already uses. Stage 5 swaps this for the
        RFC-003 ``ForecastResponse`` shape.

        Raises:
            ValueError: If ``df`` cannot be aggregated (e.g. empty
                input, missing ``date`` / ``amount`` columns).
        """
        if df.empty or "date" not in df.columns or "amount" not in df.columns:
            raise ValueError("Empty or malformed transaction dataframe")

        loader = TransactionLoader(df)
        daily_df = loader.aggregate_daily()
        if daily_df.empty:
            raise ValueError("No daily aggregates produced from input")

        recent = daily_df.tail(min(30, len(daily_df)))
        avg_daily_spend = float(recent["daily_spend"].mean()) if "daily_spend" in recent.columns else 0.0
        avg_daily_income = float(recent["daily_income"].mean()) if "daily_income" in recent.columns else 0.0

        predictions = [
            {
                "day_offset": day,
                "predicted_spend": round(avg_daily_spend, 2),
                "predicted_income": round(avg_daily_income, 2),
                "predicted_net": round(avg_daily_income - avg_daily_spend, 2),
            }
            for day in range(1, horizon + 1)
        ]

        return {
            "predictions": predictions,
            "horizon_days": horizon,
            "model": "statistical_mvp",
            "note": "Using rolling average. TFT model used when trained checkpoint available.",
        }
