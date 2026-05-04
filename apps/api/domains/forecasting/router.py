"""Forecasting router — predict spending, safe-to-spend.

Migrated from routers/forecast.py.
Fixes BUG-07: Uses parse_file() instead of parse_csv_content() to
preserve metadata columns.

Stage 5 (RFC-003): the predict endpoints now return the full
:class:`ForecastResponse` — 7-quantile points + insights +
``prediction_id``. Both ``GET`` and ``POST`` accept a ``horizon`` query
param clamped to ``[1, 30]`` (the upper bound is RFC-003 §1, NOT 90).
The legacy ``GET /forecast/safe-to-spend`` endpoint stays on the
statistical-MVP path per RFC-003 §"API Changes" pending a separate
follow-up RFC.
"""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.domains.forecasting.schemas import ForecastResponse
from apps.api.domains.forecasting.service import ForecastService
from packages.forecasting.cache import TFTModelCache
from packages.forecasting.dataset import TransactionLoader
from packages.ingestion_engine.import_transactions import parse_file
from supabase import Client

router = APIRouter(prefix="/forecast", tags=["forecast"])
logger = structlog.get_logger()


# Warm endpoint timeout — the FE expects /forecast/warm to return
# quickly with a status indicator. Anything longer than this is treated
# as ``status="warming"`` (the load is still running in the background).
WARM_BOUNDED_TIMEOUT_SECONDS = 0.5


def _get_tft_cache(request: Request) -> TFTModelCache:
    """Resolve the global ``TFTModelCache`` from ``app.state``.

    The cache is constructed once in the FastAPI lifespan
    (``apps/api/main.py``); this indirection lets tests substitute a
    mock cache via ``app.dependency_overrides``.
    """
    cache = getattr(request.app.state, "tft_cache", None)
    if cache is None:
        raise HTTPException(
            status_code=503,
            detail="TFT cache not initialised; service is starting up.",
        )
    return cache


def _warm_rate_limit(request: Request):
    """Resolve the warm-endpoint rate-limit dependency from app state."""
    dep = getattr(request.app.state, "warm_rate_limiter", None)
    if dep is None:
        return None
    return dep


def _get_service(
    request: Request,
    client: Client = Depends(get_user_client),
) -> ForecastService:
    """Construct a ForecastService scoped to the request's Supabase client.

    The TFT cache is sourced from ``app.state.tft_cache`` (constructed in
    the FastAPI lifespan); when missing (e.g. early test boot), the
    service falls back to Chronos-only.
    """
    cache = getattr(request.app.state, "tft_cache", None)
    return ForecastService(client, tft_cache=cache)


def _load_user_transactions(client: Client, user_id: str, lookback_days: int = 365) -> pd.DataFrame:
    """Fetch the user's recent transactions for the GET /predict path."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    resp = (
        client.table("transactions")
        .select("transaction_date, amount, status")
        .eq("user_id", user_id)
        .gte("transaction_date", cutoff)
        .order("transaction_date", desc=False)
        .limit(50_000)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return pd.DataFrame(columns=["date", "amount"])
    df = pd.DataFrame(rows).rename(columns={"transaction_date": "date"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    return df


@router.get("/predict", response_model=ForecastResponse)
async def forecast_predict_get(
    horizon: int = Query(30, ge=1, le=30),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    service: ForecastService = Depends(_get_service),
) -> ForecastResponse:
    """Return a forecast for the authenticated user (RFC-003 §3 contract).

    Pulls the user's transactions from Supabase, runs the tier-routed
    forecast, and returns the full :class:`ForecastResponse`. The CSV
    upload + dedup branch lives only on the ``POST`` path.
    """
    df = _load_user_transactions(client, user_id)
    try:
        return service.predict(df, user_id=user_id, horizon=horizon)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/predict", response_model=ForecastResponse)
async def forecast_predict(
    file: UploadFile = File(...),
    horizon: int = Query(30, ge=1, le=30),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    service: ForecastService = Depends(_get_service),
) -> ForecastResponse:
    """Accept a CSV of transactions and return predicted spending.

    BUG-07 fix: Uses parse_file() (preserves metadata columns) instead
    of parse_csv_content() (drops them via _normalize_dataframe).

    IMP-05 fix: Auth check and duplicate-file check happen before any
    parsing work, so duplicate uploads fail fast.

    Stage 5 (RFC-003): response shape is now :class:`ForecastResponse`;
    the dedup-by-file-hash branch on ``uploaded_files`` is preserved on
    POST only — GET has no upload tracking.
    """
    if file.content_type and "csv" not in file.content_type and "text" not in file.content_type:
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    # Parse first so a parse failure never burns a duplicate marker.
    try:
        df = parse_file(contents, file.filename)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse CSV")

    # Register upload marker after parse succeeds.
    try:
        client.table("uploaded_files").insert(
            {
                "user_id": user_id,
                "file_hash": file_hash,
                "filename": file.filename,
                "upload_type": "forecast",
            }
        ).execute()
    except Exception as e:
        if "duplicate key" in str(e) or "23505" in str(e):
            raise HTTPException(
                status_code=400,
                detail="This file has already been uploaded for forecasting.",
            )
        raise HTTPException(status_code=500, detail="Failed to register upload")

    if "transaction_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"transaction_date": "date"})

    try:
        return service.predict(df, user_id=user_id, horizon=horizon)
    except ValueError:
        # Roll back the upload marker so the user can retry with a fixed file.
        client.table("uploaded_files").delete().eq("user_id", user_id).eq("file_hash", file_hash).execute()
        raise HTTPException(status_code=400, detail="Failed to aggregate transactions")


@router.get("/safe-to-spend")
async def safe_to_spend(
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    request: Request = None,  # type: ignore[assignment]
):
    """Returns predicted safe-to-spend amount for the authenticated user."""

    horizon = 7
    lookback_days = 90

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        response = (
            client.table("transactions")
            .select("transaction_date, amount, status")
            # BUG-002 fix: Explicit user_id filter as defense-in-depth.
            # RLS on the user-scoped client already enforces isolation, but
            # this explicit filter prevents cross-tenant leakage if RLS ever
            # has a misconfiguration gap.
            .eq("user_id", user_id)
            .gte("transaction_date", cutoff)
            .order("transaction_date", desc=False)
            .limit(5000)
            .execute()
        )
        rows = response.data
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch transactions")

    if not rows:
        return {
            "safe_amount": 0.0,
            "currency": "INR",
            "horizon_days": horizon,
            "confidence": 0.0,
            "model": "statistical_mvp",
            "note": "No transactions found in the last 90 days.",
        }

    df = pd.DataFrame(rows)
    df = df.rename(columns={"transaction_date": "date"})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0)

    try:
        loader = TransactionLoader(df)
        daily_df = loader.aggregate_daily()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to aggregate transactions")

    days_of_data = len(daily_df)
    confidence = round(min(days_of_data / lookback_days, 1.0), 2)
    recent = daily_df.tail(min(30, len(daily_df)))

    model_name = "statistical_mvp"
    model_note = f"Based on {days_of_data} days of transaction history."

    avg_daily_income = float(recent["daily_income"].mean()) if "daily_income" in recent.columns else 0.0
    avg_daily_spend = float(recent["daily_spend"].mean()) if "daily_spend" in recent.columns else 0.0
    net = (avg_daily_income - avg_daily_spend) * horizon
    safe_amount = round(max(0.0, net), 2)
    projected_overspend = round(max(0.0, -net), 2)
    forecast_breakdown = []

    # Stage 5: migrate from the deleted ``inference._MODEL_CACHE`` /
    # ``load_model`` shims to the bounded TFT cache via
    # ``cache.get_or_load(user_id)`` (RFC-004). When the cache is
    # unavailable (test boot path that doesn't set ``app.state.tft_cache``)
    # or the loader returns ``None`` (no trained model yet), this falls
    # back to the statistical-MVP path above.
    try:
        cache = getattr(request.app.state, "tft_cache", None) if request is not None else None
        cached = await cache.get_or_load(user_id) if cache is not None else None
        if cached is not None and cached.model is not None and len(daily_df) >= 60:
            from packages.forecasting.inference import predict_with_tft

            pred_data = predict_with_tft(cached.model, df, horizon=horizon)
            if "forecast" in pred_data:
                forecast = pred_data["forecast"]
                total_predicted_spend_p90 = sum(day.get("p90", 0) for day in forecast)
                total_predicted_income = avg_daily_income * horizon
                tft_net = total_predicted_income - total_predicted_spend_p90
                safe_amount = round(max(0.0, tft_net), 2)
                projected_overspend = round(max(0.0, -tft_net), 2)
                model_name = "tft_v1"
                model_note = "AI prediction (TFT) for spending, statistical avg for income."
                forecast_breakdown = forecast
    except Exception as e:
        logger.warning("tft_inference_failed", error=str(e))

    return {
        "safe_amount": safe_amount,
        "projected_overspend": projected_overspend,
        "currency": "INR",
        "horizon_days": horizon,
        "confidence": confidence,
        "avg_daily_income": round(avg_daily_income, 2),
        "avg_daily_spend": round(avg_daily_spend, 2),
        "days_analyzed": days_of_data,
        "model": model_name,
        "note": model_note,
        "forecast_breakdown": forecast_breakdown,
    }


@router.post("/warm", status_code=202)
async def warm_model(
    request: Request,
    user_id: str = Depends(get_current_user_id),
    cache: TFTModelCache = Depends(_get_tft_cache),
):
    """Pre-warm the TFT model for the current user.

    Per RFC-004 §3 + §Codex Fix #4: the request races a bounded-wait
    against ``cache.get_or_load`` — if the load completes within the
    bounded window we return ``status="ready"``, otherwise the load is
    detached as a background task and we return ``status="warming"``
    immediately so the FE can race ``predict`` against the warm.

    Rate-limited to 1 call per 5 minutes per user via the existing
    ``RateLimiter + rate_limit_dependency`` pattern (see
    ``apps/api/main.py`` lifespan).
    """
    # Apply rate limit (constructed in app.state; see lifespan).
    dep = _warm_rate_limit(request)
    if dep is not None:
        await dep(request)

    async def _load_and_log() -> None:
        try:
            await cache.get_or_load(user_id)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("tft_warm_task_failed", user_id=user_id, error=str(exc))

    try:
        result = await asyncio.wait_for(
            cache.get_or_load(user_id),
            timeout=WARM_BOUNDED_TIMEOUT_SECONDS,
        )
        status = "ready" if result is not None else "failed"
        return {"status": status, "user_id": user_id}
    except asyncio.TimeoutError:
        # The load is still in flight on the cache's _inflight table;
        # it will complete in the background and populate the cache.
        # Detach a follower task so the load is not abandoned.
        asyncio.create_task(_load_and_log())
        return {"status": "warming", "user_id": user_id}
    except Exception as exc:
        logger.warning("tft_warm_failed", user_id=user_id, error=str(exc))
        return {"status": "failed", "user_id": user_id}
