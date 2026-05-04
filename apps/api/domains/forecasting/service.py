"""Forecasting service — RFC-003 §3 implementation.

Tier-routes between Chronos-2 (cold-start, <90 days history), Chronos
fallback (>=90 days but no warm cache entry), and the
TFT-Hybrid + Chronos ensemble (>=90 days + warm cache hit). Builds the
RFC-003 :class:`ForecastResponse`, computes derived insights, generates
``prediction_id`` BEFORE the fire-and-forget log INSERT, and atomically
dedups via the ``log_user_prediction`` SECURITY DEFINER RPC.

The log RPC is fire-and-forget: a failure is caught, logged, the
Prometheus counter ``forecast_log_insert_failures_total`` is bumped,
and the user still receives a valid response (with a real
``prediction_id``).

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §3, §3b
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import structlog

from apps.api.core.metrics import forecast_log_insert_failures_total
from apps.api.domains.forecasting.schemas import (
    ForecastPoint,
    ForecastResponse,
    VariableImportance,
)
from packages.forecasting.chronos_engine import QUANTILE_LABELS, get_chronos_engine
from packages.forecasting.dataset import TransactionLoader
from packages.forecasting.ensemble import ensemble_forecasts
from packages.forecasting.inference import extract_variable_importance, predict_with_tft
from packages.forecasting.insights import (
    INSIGHTS_VERSION,
    _safe_default_insights,
    compute_insights,
)

logger = structlog.get_logger(__name__)

COLD_START_THRESHOLD: int = 90  # days


def _compute_confidence(days_of_data: int, *, has_model: bool = False) -> str:
    """Map ``days_of_data`` + model availability → confidence bucket."""
    if days_of_data <= 30:
        return "low"
    if has_model and days_of_data >= COLD_START_THRESHOLD:
        return "high"
    return "medium"


def _forecast_dict_to_matrix(forecast: list[dict[str, Any]]) -> tuple[np.ndarray, list[str]]:
    """Convert engine forecast dicts to a ``(horizon, 7)`` numpy matrix + dates."""
    rows = []
    dates: list[str] = []
    for entry in forecast:
        rows.append([float(entry[q]) for q in QUANTILE_LABELS])
        dates.append(str(entry.get("date", "")))
    return np.asarray(rows, dtype=float), dates


class ForecastService:
    """Forecast service — runs the model tier router + logs each call.

    Args:
        client: User-scoped Supabase client (the JWT-bearing client per
            RFC-003 §4 — the ``users insert own predictions`` RLS policy
            + RPC SECURITY DEFINER allow user-scoped INSERTs).
        tft_cache: Optional :class:`TFTModelCache` instance. When
            supplied, the service uses ``cache.get_or_load(user_id)`` to
            resolve the user's model. When ``None``, the service skips
            the TFT path and emits Chronos-only forecasts.
    """

    def __init__(self, client: Any, tft_cache: Any = None) -> None:
        self.client = client
        self.tft_cache = tft_cache

    # ------------------------------------------------------------------ #
    # Public surface
    # ------------------------------------------------------------------ #

    def predict(
        self,
        transactions_df: pd.DataFrame,
        *,
        user_id: str,
        horizon: int = 30,
    ) -> ForecastResponse:
        """Run the tier-routed forecast for ``user_id`` over ``horizon`` days.

        The synchronous predict path: aggregate → tier-route → run model →
        compute insights → assemble response → fire-and-forget log →
        return response. Logging never blocks; insight computation is
        guarded with a fallback to ``_safe_default_insights``.

        Raises:
            ValueError: When ``transactions_df`` is empty or malformed
                so aggregation cannot proceed.
        """
        if transactions_df is None or transactions_df.empty:
            raise ValueError("Empty transaction dataframe")
        if "date" not in transactions_df.columns or "amount" not in transactions_df.columns:
            raise ValueError("Transactions DataFrame missing 'date' or 'amount'")

        loader = TransactionLoader(transactions_df)
        daily_df = loader.aggregate_daily()
        if daily_df.empty:
            raise ValueError("No daily aggregates produced from input")

        days_of_data = len(daily_df)

        # ------------------------------------------------------------------
        # Tier 1 — always run Chronos-2 baseline.
        # ------------------------------------------------------------------
        chronos = get_chronos_engine()
        # Chronos requires `closing_balance` in daily_df (provided by
        # aggregate_daily()).
        chronos_df = daily_df.reset_index() if daily_df.index.name == "date" else daily_df
        chronos_result = chronos.predict(chronos_df, horizon=horizon)

        # ------------------------------------------------------------------
        # Tier 2 — TFT path only if (a) cache configured, (b) >=90 days,
        # (c) cache hit. Otherwise stay on Chronos.
        # ------------------------------------------------------------------
        cached = None
        if self.tft_cache is not None and days_of_data >= COLD_START_THRESHOLD:
            cached = self._safe_get_cached_model(user_id)

        var_importance: list[VariableImportance] | None = None
        final_result: dict[str, Any]

        if cached is not None:
            try:
                tft_result = predict_with_tft(cached.model, transactions_df, horizon=horizon)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("tft_inference_raised", user_id=user_id, error=str(exc))
                tft_result = {"error": str(exc)}

            if "error" in tft_result:
                logger.warning("tft_inference_failed", user_id=user_id, error=tft_result["error"])
                final_result = chronos_result
            else:
                try:
                    raw_vi = extract_variable_importance(cached.model, transactions_df)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("vi_extraction_raised", user_id=user_id, error=str(exc))
                    raw_vi = None
                if raw_vi:
                    var_importance = [VariableImportance(**vi) for vi in raw_vi]
                final_result = ensemble_forecasts(tft_result, chronos_result)
        else:
            final_result = chronos_result

        has_model = cached is not None and final_result.get("model_type") == "ensemble"
        confidence = _compute_confidence(days_of_data, has_model=has_model)

        # ------------------------------------------------------------------
        # Insights — guarded; fallback to safe defaults on any failure.
        # ------------------------------------------------------------------
        forecast_list = final_result.get("forecast", [])
        matrix, future_date_strs = _forecast_dict_to_matrix(forecast_list)
        future_dates = [pd.Timestamp(d).date() if d else pd.Timestamp.now().date() for d in future_date_strs]

        try:
            history_for_insights = (
                chronos_df.copy() if "closing_balance" in chronos_df.columns else daily_df.reset_index()
            )
            vi_dict = {item.feature: item.weight for item in var_importance} if var_importance else None
            insights = compute_insights(
                forecast_matrix=matrix,
                future_dates=future_dates,
                history_df=history_for_insights,
                variable_importance=vi_dict,
                user_floor_override=None,
            )
        except Exception as exc:
            logger.warning("insights_compute_failed", user_id=user_id, error=str(exc))
            insights = _safe_default_insights()

        # ------------------------------------------------------------------
        # Assemble response.
        # ------------------------------------------------------------------
        prediction_id = uuid4()
        forecast_points = [ForecastPoint(**entry) for entry in forecast_list]

        response = ForecastResponse(
            forecast=forecast_points,
            model_type=final_result.get("model_type", "chronos2"),
            model_version=str(final_result.get("model_version", "chronos-2-small")),
            horizon=horizon,
            confidence=confidence,
            variable_importance=var_importance,
            insights=insights,
            prediction_id=prediction_id,
        )

        # ------------------------------------------------------------------
        # Fire-and-forget log via RPC. RPC failure is non-fatal.
        # ------------------------------------------------------------------
        self._log_prediction(prediction_id=prediction_id, user_id=user_id, response=response)

        return response

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _safe_get_cached_model(self, user_id: str) -> Any:
        """Resolve the user's TFT model from cache, swallowing all errors.

        ``TFTModelCache.get_or_load`` is async; we drive it via
        ``asyncio.run`` (single short-lived loop) when called from a
        synchronous request handler. Any failure (no model trained,
        loader raised, cache misconfigured) returns ``None`` so the
        caller falls back to Chronos-only.
        """
        import asyncio

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None and loop.is_running():
                # Running inside an event loop already — schedule on it.
                # This path is only hit by tests that run predict inside
                # asyncio.run; in production /forecast/predict is a sync
                # def handler so we hit the asyncio.run path below.
                future = asyncio.run_coroutine_threadsafe(self.tft_cache.get_or_load(user_id), loop)
                return future.result(timeout=30)

            return asyncio.run(self.tft_cache.get_or_load(user_id))
        except Exception as exc:
            logger.warning("tft_cache_load_failed", user_id=user_id, error=str(exc))
            return None

    def _log_prediction(self, *, prediction_id: Any, user_id: str, response: ForecastResponse) -> None:
        """Fire-and-forget INSERT into ``user_predictions`` via RPC.

        Per RFC-003 §3b, the RPC enforces atomic dedup at the DB layer
        (UNIQUE (user_id, generated_hour) + ON CONFLICT DO NOTHING).
        The boolean RPC return (``true`` = inserted, ``false`` = dedup
        skipped) is discarded — the service already holds
        ``prediction_id`` from ``uuid4()``, which RFC-003 requires the
        response to carry regardless of DB write outcome.
        """
        try:
            payload = {
                "prediction_id": str(prediction_id),
                "user_id": user_id,
                "model_type": response.model_type,
                "model_version": response.model_version,
                "horizon_days": response.horizon,
                "forecast": [point.model_dump() for point in response.forecast],
                "variable_importance": (
                    [vi.model_dump() for vi in response.variable_importance] if response.variable_importance else None
                ),
                "insights": response.insights.model_dump(),
                "insights_version": INSIGHTS_VERSION,
                "shown_to_user": True,
            }
            self.client.rpc("log_user_prediction", {"payload": payload}).execute()
        except Exception as exc:
            forecast_log_insert_failures_total.inc()
            logger.warning(
                "prediction_log_failed",
                user_id=user_id,
                prediction_id=str(prediction_id),
                error=str(exc),
            )
