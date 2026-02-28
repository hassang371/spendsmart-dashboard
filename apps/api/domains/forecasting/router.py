"""Forecasting router — predict spending, safe-to-spend.

Migrated from routers/forecast.py.
Fixes BUG-07: Uses parse_file() instead of parse_csv_content() to
preserve metadata columns.
"""

import hashlib
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from supabase import Client

from apps.api.core.auth import get_user_client
from packages.forecasting.dataset import TransactionLoader
from packages.forecasting.inference import load_model, predict_with_tft
from packages.ingestion_engine.import_transactions import parse_file

router = APIRouter(prefix="/forecast", tags=["forecast"])
logger = structlog.get_logger()


@router.post("/predict")
async def forecast_predict(
    file: UploadFile = File(...),
    client: Client = Depends(get_user_client),
):
    """Accept a CSV of transactions and return predicted spending.

    BUG-07 fix: Uses parse_file() (preserves metadata columns) instead
    of parse_csv_content() (drops them via _normalize_dataframe).
    """
    if (
        file.content_type
        and "csv" not in file.content_type
        and "text" not in file.content_type
    ):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    contents = await file.read()
    file_hash = hashlib.sha256(contents).hexdigest()

    try:
        # BUG-07 fix: use parse_file instead of parse_csv_content
        df = parse_file(contents, file.filename)
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to parse CSV")

    if "transaction_date" in df.columns and "date" not in df.columns:
        df = df.rename(columns={"transaction_date": "date"})

    try:
        loader = TransactionLoader(df)
        daily_df = loader.aggregate_daily()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to aggregate transactions")

    # Register upload hash
    try:
        user_response = client.auth.get_user()
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Invalid bearer token")
        client.table("uploaded_files").insert({
            "user_id": user_response.user.id,
            "file_hash": file_hash,
            "filename": file.filename,
            "upload_type": "forecast",
        }).execute()
    except Exception as e:
        if "duplicate key" in str(e) or "23505" in str(e):
            raise HTTPException(
                status_code=400,
                detail="This file has already been uploaded for forecasting.",
            )
        raise HTTPException(status_code=500, detail="Failed to register upload")

    # Statistical forecast
    horizon = 7
    recent = daily_df.tail(min(30, len(daily_df)))
    avg_daily_spend = (
        float(recent["daily_spend"].mean()) if "daily_spend" in recent.columns else 0.0
    )
    avg_daily_income = (
        float(recent["daily_income"].mean()) if "daily_income" in recent.columns else 0.0
    )

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


@router.get("/safe-to-spend")
async def safe_to_spend(client: Client = Depends(get_user_client)):
    """Returns predicted safe-to-spend amount for the authenticated user."""
    horizon = 7
    lookback_days = 90

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
        response = (
            client.table("transactions")
            .select("transaction_date, amount, status")
            .gte("transaction_date", cutoff)
            .order("transaction_date", desc=False)
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

    user_resp = client.auth.get_user()
    user_id = user_resp.user.id if user_resp and user_resp.user else None

    model_name = "statistical_mvp"
    model_note = f"Based on {days_of_data} days of transaction history."

    avg_daily_income = (
        float(recent["daily_income"].mean()) if "daily_income" in recent.columns else 0.0
    )
    avg_daily_spend = (
        float(recent["daily_spend"].mean()) if "daily_spend" in recent.columns else 0.0
    )
    safe_amount = round((avg_daily_income - avg_daily_spend) * horizon, 2)
    forecast_breakdown = []

    if user_id:
        try:
            tft_model = load_model(client, user_id)
            if tft_model and len(daily_df) >= 60:
                pred_data = predict_with_tft(tft_model, df, horizon=horizon)
                if "forecast" in pred_data:
                    forecast = pred_data["forecast"]
                    total_predicted_spend_p90 = sum(
                        day.get("p90", 0) for day in forecast
                    )
                    total_predicted_income = avg_daily_income * horizon
                    safe_amount = round(
                        total_predicted_income - total_predicted_spend_p90, 2
                    )
                    model_name = "tft_v1"
                    model_note = "AI prediction (TFT) for spending, statistical avg for income."
                    forecast_breakdown = forecast
        except Exception as e:
            logger.warning("tft_inference_failed", error=str(e))

    return {
        "safe_amount": safe_amount,
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
