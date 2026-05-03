"""Forecasting router — predict spending, safe-to-spend.

Migrated from routers/forecast.py.
Fixes BUG-07: Uses parse_file() instead of parse_csv_content() to
preserve metadata columns.

Stage 1 (LLD 009) refactor: the POST /predict handler is now a thin
delegation layer over ``ForecastService`` (apps/api/domains/forecasting/
service.py). The over-the-wire response shape is unchanged — Stage 5
(RFC-003) is the migration that swaps the response_model to the new
``ForecastResponse``.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from apps.api.core.auth import get_current_user_id, get_user_client
from apps.api.domains.forecasting.service import ForecastService
from packages.forecasting.dataset import TransactionLoader
from packages.forecasting.inference import load_model, predict_with_tft
from packages.ingestion_engine.import_transactions import parse_file
from supabase import Client

router = APIRouter(prefix="/forecast", tags=["forecast"])
logger = structlog.get_logger()


def _get_service(client: Client = Depends(get_user_client)) -> ForecastService:
    """Construct a ForecastService scoped to the request's Supabase client."""
    return ForecastService(client)


@router.post("/predict")
async def forecast_predict(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
    service: ForecastService = Depends(_get_service),
):
    """Accept a CSV of transactions and return predicted spending.

    BUG-07 fix: Uses parse_file() (preserves metadata columns) instead
    of parse_csv_content() (drops them via _normalize_dataframe).

    IMP-05 fix: Auth check and duplicate-file check happen before any
    parsing work, so duplicate uploads fail fast.

    Stage 1: forecast computation now lives in ``ForecastService.predict``;
    this handler is responsible only for transport concerns (CSV parse,
    upload-dedup, error mapping).
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
        return service.predict(df, user_id=user_id, horizon=7)
    except ValueError:
        # Roll back the upload marker so the user can retry with a fixed file.
        client.table("uploaded_files").delete().eq("user_id", user_id).eq("file_hash", file_hash).execute()
        raise HTTPException(status_code=400, detail="Failed to aggregate transactions")


@router.get("/safe-to-spend")
async def safe_to_spend(
    user_id: str = Depends(get_current_user_id),
    client: Client = Depends(get_user_client),
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

    try:
        tft_model = load_model(client, user_id)
        if tft_model and len(daily_df) >= 60:
            pred_data = predict_with_tft(tft_model, df, horizon=horizon)
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
