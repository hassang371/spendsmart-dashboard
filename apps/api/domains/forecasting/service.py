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

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import structlog

from apps.api.core.metrics import forecast_log_insert_failures_total
from apps.api.domains.forecasting.schemas import (
    ForecastPoint,
    ForecastResponse,
    IntentConfidence,
    IntentCreateRequest,
    IntentType,
    ScenarioDelta,
    ScenarioResponse,
    UserIntent,
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


def _compute_scenario_delta(*, a: ForecastResponse, b: ForecastResponse) -> ScenarioDelta:
    """Compute B − A on the six comparable insight metrics."""
    ai = a.insights
    bi = b.insights
    return ScenarioDelta(
        safe_to_spend=float(bi.safe_to_spend - ai.safe_to_spend),
        overdraft_risk_score=float(bi.overdraft_risk_score - ai.overdraft_risk_score),
        predicted_monthly_spend=float(bi.predicted_monthly_spend - ai.predicted_monthly_spend),
        predicted_monthly_income=float(bi.predicted_monthly_income - ai.predicted_monthly_income),
        month_end_p50_delta=float(bi.month_end.p50 - ai.month_end.p50),
        confidence_band_width_delta=float(bi.confidence_band_width - ai.confidence_band_width),
    )


def _filter_widener_intents(intents: list[UserIntent]) -> list[UserIntent]:
    """LLD 010 — pick the intents that should enter RFC-005's widener list.

    Per the LLD: ``LIFE_EVENT`` always widens (a baby is unpredictable
    even when you're sure it's coming); plus any non-LIFE_EVENT intent at
    ``low`` or ``medium`` confidence.

    Inactive intents are skipped — soft-deleted intents must not affect
    the forecast.
    """
    out: list[UserIntent] = []
    for i in intents:
        if not i.is_active:
            continue
        if i.intent_type is IntentType.LIFE_EVENT:
            out.append(i)
        elif i.confidence in (IntentConfidence.LOW, IntentConfidence.MEDIUM):
            out.append(i)
    return out


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
        active_intents: list[UserIntent] | None = None,
        log_prediction: bool = True,
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

        # Auto-trigger TFT training when user is eligible but no model is
        # warm. Best-effort + idempotent — duplicate enqueues are skipped.
        if cached is None:
            self._maybe_enqueue_training(user_id, days_of_data)

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
            # LLD 010 — propagate active intents to the widener. Default
            # path fetches stored intents from supabase; scenario_predict
            # passes an explicit list (baseline / counterfactual).
            if active_intents is None:
                stored = self._fetch_active_intents(user_id)
            else:
                stored = active_intents
            widener_intents = _filter_widener_intents(stored)
            insights = compute_insights(
                forecast_matrix=matrix,
                future_dates=future_dates,
                history_df=history_for_insights,
                variable_importance=vi_dict,
                user_floor_override=None,
                active_intents=widener_intents or None,
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
        # Scenario forecasts pass log_prediction=False — RFC-003 §4 dedups
        # one row per (user, hour), so logging hypothetical A/B forecasts
        # would pollute that table.
        # ------------------------------------------------------------------
        if log_prediction:
            self._log_prediction(prediction_id=prediction_id, user_id=user_id, response=response)

        return response

    async def scenario_predict(
        self,
        transactions_df: pd.DataFrame,
        *,
        user_id: str,
        excludes: list[Any] | None = None,
        ephemeral: list[IntentCreateRequest] | None = None,
        horizon: int = 30,
    ) -> ScenarioResponse:
        """A/B forecast comparison — LLD 010 §Scenario Endpoint Design.

        Runs two forecasts concurrently:
          * ``without_intents`` (A) — baseline = stored active intents
            minus ``excludes``.
          * ``with_intents`` (B) — A plus ``ephemeral`` (transient,
            never persisted).

        Computes the field-by-field delta (B − A) on the comparable
        insight metrics. Does NOT log either forecast to
        ``user_predictions`` — that table is reserved for the production
        ``predict`` path (RFC-003 §4).
        """
        excludes = excludes or []
        ephemeral = ephemeral or []
        exclude_ids = {str(eid) for eid in excludes}

        stored = self._fetch_active_intents(user_id)
        kept = [i for i in stored if str(i.id) not in exclude_ids]
        excluded = [i for i in stored if str(i.id) in exclude_ids]

        # Materialise ephemeral intents as transient UserIntent objects
        # so the same widener filter applies. They never touch the DB.
        from uuid import uuid4

        ephemeral_intents = [
            UserIntent(
                id=uuid4(),
                user_id=uuid4(),
                intent_type=req.intent_type,
                amount=req.amount,
                amount_delta=req.amount_delta,
                category_bucket=req.category_bucket,
                start_date=req.start_date,
                end_date=req.end_date,
                confidence=req.confidence,
                is_recurring=req.is_recurring,
                rrule_freq=req.rrule_freq,
                notes=req.notes,
                is_active=True,
                created_at="1970-01-01T00:00:00+00:00",
                updated_at="1970-01-01T00:00:00+00:00",
            )
            for req in ephemeral
        ]

        applied = kept + ephemeral_intents

        loop = asyncio.get_running_loop()

        def _run_predict(active: list[UserIntent]) -> ForecastResponse:
            return self.predict(
                transactions_df,
                user_id=user_id,
                horizon=horizon,
                active_intents=active,
                log_prediction=False,
            )

        # Concurrency: run both forecasts in parallel via threadpool —
        # predict() is sync (not async). asyncio.gather schedules the
        # two thread executions concurrently.
        without_task = loop.run_in_executor(None, _run_predict, kept)
        with_task = loop.run_in_executor(None, _run_predict, applied)
        without_resp, with_resp = await asyncio.gather(without_task, with_task)

        delta = _compute_scenario_delta(a=without_resp, b=with_resp)
        return ScenarioResponse(
            with_intents=with_resp,
            without_intents=without_resp,
            delta=delta,
            applied_intents=applied,
            excluded_intents=excluded,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _fetch_active_intents(self, user_id: str) -> list[UserIntent]:
        """Read the user's active intents via the user-scoped client.

        Returns ``[]`` on any failure (no intents table yet, RLS gap,
        transient supabase error). The forecast must continue even
        when the intent table is unavailable — backward compatibility
        per LLD 010 §Success Criteria.
        """
        try:
            resp = self.client.table("user_intents").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            rows = resp.data or []
            return [UserIntent(**row) for row in rows]
        except Exception as exc:
            logger.warning("fetch_active_intents_failed", user_id=user_id, error=str(exc))
            return []

    def _maybe_enqueue_training(self, user_id: str, days_of_data: int) -> None:
        """Best-effort: enqueue a TFT training job when user is eligible
        and no recent active or completed forecasting job blocks it.

        Worker recognises forecasting jobs via the ``logs`` prefix
        ``forecasting:`` (per ``apps/worker/main.py::process_next_job``;
        ``training_jobs`` has no ``job_type`` column).

        Failure is non-fatal — the predict path stays on Chronos cold-start.
        """
        if days_of_data < COLD_START_THRESHOLD:
            return
        try:
            # BUG-020: skip if ANY active job exists. Worker overwrites
            # logs once it claims, so the `forecasting:autoenq` marker
            # disappears — using it as a filter let duplicate enqueues
            # through and produced storms of stale `processing` rows.
            active = (
                self.client.table("training_jobs")
                .select("id")
                .eq("user_id", user_id)
                .in_("status", ["pending", "queued", "running", "processing"])
                .limit(1)
                .execute()
            )
            if active.data:
                return  # Some training job is already in flight.

            cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
            recent_complete = (
                self.client.table("training_jobs")
                .select("id, logs")
                .eq("user_id", user_id)
                .eq("status", "completed")
                .gte("created_at", cutoff)
                .limit(20)
                .execute()
            )
            if any(str(row.get("logs") or "").startswith("forecasting:") for row in (recent_complete.data or [])):
                return  # Recently retrained — let the model sit for now.

            self.client.table("training_jobs").insert(
                {
                    "user_id": user_id,
                    "status": "pending",
                    "logs": "forecasting:autoenq",
                }
            ).execute()
            logger.info("training_auto_enqueued", user_id=user_id, days=days_of_data)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("training_auto_enqueue_failed", user_id=user_id, error=str(exc))

    def _safe_get_cached_model(self, user_id: str) -> Any:
        """Resolve the user's TFT model from cache, swallowing all errors.

        Uses the loop-agnostic ``get_or_load_sync`` (BUG-024) wrapped in
        a daemon thread so a slow checkpoint download cannot block the
        FastAPI serving loop. The previous async path tied the cache's
        ``asyncio.Lock`` to the subscriber's loop and broke whenever a
        fresh-loop thread tried to acquire it.
        """
        import threading

        result_box: list[Any] = [None]
        err_box: list[BaseException | None] = [None]

        def _runner() -> None:
            try:
                result_box[0] = self.tft_cache.get_or_load_sync(user_id)
            except BaseException as exc:  # noqa: BLE001
                err_box[0] = exc

        t = threading.Thread(target=_runner, name=f"tft-cache-load:{user_id}", daemon=True)
        t.start()
        t.join(timeout=60)

        if t.is_alive():
            logger.warning("tft_cache_load_timeout", user_id=user_id)
            return None
        if err_box[0] is not None:
            exc = err_box[0]
            logger.warning(
                "tft_cache_load_failed",
                user_id=user_id,
                error=f"{type(exc).__name__}: {exc}",
            )
            return None
        return result_box[0]

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
