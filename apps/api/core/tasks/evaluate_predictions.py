"""``evaluate_past_predictions`` Celery beat task (RFC-003 §5).

For each ``user_predictions`` row whose ``horizon_end`` is in the past
and whose ``evaluated_at`` is still NULL, fetch the user's actual
transactions over ``[generated_at::date, horizon_end]``, compute the
per-day actual closing-balance trajectory, then write
``actual_outcomes`` + per-quantile ``pinball_loss`` + P50 ``mape`` to
the row.

The claim query is the **lease pattern** from RFC-003 §5 (Codex Fix
#2): ``UPDATE … FOR UPDATE SKIP LOCKED`` with a 15-minute lease so a
crashed worker's rows are recoverable on the next beat fire. The
fill-in UPDATE is the only write that sets ``evaluated_at = now()``.

Per-row failures are isolated — one row throwing does not abort the
batch. The thrown row's lease expires in ≤15 min and the next beat
fire re-claims it.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §5
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import structlog
from celery import shared_task

from apps.api.core.tasks.maintenance_tasks import get_service_client

logger = structlog.get_logger(__name__)

CLAIM_BATCH_SIZE: int = 100
LEASE_MINUTES: int = 15


# ---------------------------------------------------------------------------
# Pure-math helpers (also exported for unit tests)
# ---------------------------------------------------------------------------


QUANTILE_LEVELS: dict[str, float] = {
    "p2": 0.02,
    "p10": 0.10,
    "p25": 0.25,
    "p50": 0.50,
    "p75": 0.75,
    "p90": 0.90,
    "p98": 0.98,
}


def compute_pinball_loss(
    y_true: list[float],
    forecasts: list[dict[str, float]],
) -> dict[str, float]:
    """Per-quantile pinball loss across the horizon.

    Pinball loss for quantile ``q`` and pair ``(y, y_q)``:
        ``L_q(y, y_q) = max(q * (y - y_q), (q - 1) * (y - y_q))``

    Returns the mean pinball loss for each of the seven RFC-003 quantiles.
    """
    out: dict[str, float] = {}
    if not y_true or not forecasts or len(y_true) != len(forecasts):
        return {key: 0.0 for key in QUANTILE_LEVELS}

    for key, q in QUANTILE_LEVELS.items():
        total = 0.0
        for actual, fc in zip(y_true, forecasts):
            y_q = float(fc[key])
            diff = float(actual) - y_q
            total += max(q * diff, (q - 1) * diff)
        out[key] = total / len(y_true)
    return out


def compute_mape(y_true: list[float], y_pred: list[float]) -> float | None:
    """Mean absolute percentage error on the P50 vs actual pair.

    Returns ``None`` when *every* truth value is zero (division by zero
    edge case for a constant-zero-balance user). This is recorded as
    NULL in the DB ``mape`` column.
    """
    if not y_true or len(y_true) != len(y_pred):
        return None

    accum = 0.0
    counted = 0
    for actual, pred in zip(y_true, y_pred):
        if actual == 0:
            continue
        accum += abs((float(actual) - float(pred)) / float(actual))
        counted += 1
    if counted == 0:
        return None
    return accum / counted


# ---------------------------------------------------------------------------
# Per-row evaluation
# ---------------------------------------------------------------------------


def _fetch_actual_balances(supabase, user_id: str, start_date: str, end_date: str) -> list[float]:
    """Fetch the user's daily closing balances over ``[start_date, end_date]``.

    Returns a list of floats keyed off the dates between the two
    bounds; when the user has no transactions, returns ``[]``.
    """
    resp = (
        supabase.table("transactions")
        .select("transaction_date, amount")
        .eq("user_id", user_id)
        .gte("transaction_date", start_date)
        .lte("transaction_date", end_date)
        .order("transaction_date", desc=False)
        .limit(50_000)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return []

    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"]).dt.date
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    daily = df.groupby("transaction_date")["amount"].sum().sort_index()

    # Reindex to dense daily index between the bounds.
    full_idx = pd.date_range(start_date, end_date, freq="D").date
    daily = daily.reindex(full_idx, fill_value=0.0)
    closing = daily.cumsum()
    return [float(v) for v in closing.tolist()]


def _evaluate_row(supabase, row: dict[str, Any]) -> bool:
    """Compute + write metrics for one claimed row. Returns True on success."""
    prediction_id = row["prediction_id"]
    user_id = row["user_id"]
    horizon_days = int(row["horizon_days"])
    forecast = row["forecast"]
    generated_at = row["generated_at"]

    if isinstance(generated_at, str):
        gen_dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    else:
        gen_dt = generated_at
    start_date = gen_dt.date().isoformat()
    end_date = pd.Timestamp(gen_dt.date()) + pd.Timedelta(days=horizon_days)
    end_date_str = end_date.date().isoformat()

    actuals = _fetch_actual_balances(supabase, user_id, start_date, end_date_str)

    if not actuals:
        # User has no transactions in the horizon — record a sentinel
        # so the row leaves the unevaluated index.
        update = {
            "actual_outcomes": {"note": "no_data"},
            "mape": None,
            "pinball_loss": None,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "claimed_at": None,
            "lease_expires_at": None,
        }
        supabase.table("user_predictions").update(update).eq("prediction_id", prediction_id).execute()
        return True

    # Align lengths — actuals may be a different length than the
    # forecast list when the user has partial coverage.
    n = min(len(actuals), len(forecast))
    actuals = actuals[:n]
    forecast = forecast[:n]

    p50 = [float(fc["p50"]) for fc in forecast]
    pinball = compute_pinball_loss(actuals, forecast)
    mape = compute_mape(actuals, p50)

    update = {
        "actual_outcomes": {"closing_balance": actuals},
        "mape": mape,
        "pinball_loss": pinball,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "claimed_at": None,
        "lease_expires_at": None,
    }
    supabase.table("user_predictions").update(update).eq("prediction_id", prediction_id).execute()
    return True


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@shared_task(name="evaluate_past_predictions")
def evaluate_past_predictions() -> dict[str, int]:
    """Daily evaluation pass over matured ``user_predictions`` rows.

    Returns a small dict of counters for observability.
    """
    supabase = get_service_client()
    logger.info("evaluate_past_predictions_start")

    # Pass 1 — atomic claim. We use raw SQL via the supabase RPC layer
    # because the postgrest fluent API does not expose ``FOR UPDATE
    # SKIP LOCKED``. The migration in 20260418400000 indexes this
    # query's primary filter.
    claim_sql = """
    WITH claimable AS (
        SELECT prediction_id
        FROM public.user_predictions
        WHERE evaluated_at IS NULL
          AND horizon_end <= now()::date
          AND (claimed_at IS NULL OR lease_expires_at < now())
        ORDER BY horizon_end
        LIMIT %(limit)s
        FOR UPDATE SKIP LOCKED
    )
    UPDATE public.user_predictions up
    SET claimed_at       = now(),
        lease_expires_at = now() + interval '%(lease_minutes)s minutes'
    FROM claimable c
    WHERE up.prediction_id = c.prediction_id
    RETURNING up.prediction_id, up.user_id, up.generated_at, up.horizon_days, up.forecast;
    """

    try:
        # Most Supabase Python clients don't expose raw SQL; project
        # convention is to define a SECURITY DEFINER helper. If the
        # helper is missing, fall back to the naïve postgrest filter
        # (no lease) — Stage 10 wires the SQL helper.
        resp = supabase.rpc(
            "claim_predictions_for_evaluation",
            {"limit_n": CLAIM_BATCH_SIZE, "lease_minutes": LEASE_MINUTES},
        ).execute()
        claimed = resp.data or []
    except Exception as exc:
        logger.warning("claim_rpc_unavailable_falling_back", error=str(exc))
        claimed = _claim_via_postgrest(supabase)

    succeeded = 0
    failed = 0
    for row in claimed:
        try:
            if _evaluate_row(supabase, row):
                succeeded += 1
        except Exception as exc:
            failed += 1
            logger.warning(
                "evaluate_row_failed",
                prediction_id=row.get("prediction_id"),
                error=str(exc),
            )
            # Lease will expire in 15 min; next beat fire re-claims.

    logger.info(
        "evaluate_past_predictions_done",
        claimed=len(claimed),
        succeeded=succeeded,
        failed=failed,
    )
    return {"claimed": len(claimed), "succeeded": succeeded, "failed": failed}


def _claim_via_postgrest(supabase) -> list[dict[str, Any]]:
    """Fallback claim path when the SQL helper is unavailable.

    Not atomic across concurrent workers (no ``FOR UPDATE SKIP
    LOCKED``); intended only as a development aid until the helper is
    wired in Stage 10. Uses a write-the-lease-then-read pattern; rows
    whose lease has expired are re-claimable.
    """
    cutoff_iso = datetime.now(timezone.utc).isoformat()
    fetch = (
        supabase.table("user_predictions")
        .select("prediction_id, user_id, generated_at, horizon_days, forecast, claimed_at, lease_expires_at")
        .is_("evaluated_at", None)
        .lte("horizon_end", cutoff_iso[:10])
        .or_(f"claimed_at.is.null,lease_expires_at.lt.{cutoff_iso}")
        .order("horizon_end", desc=False)
        .limit(CLAIM_BATCH_SIZE)
        .execute()
    )
    rows = fetch.data or []
    if not rows:
        return []

    new_lease = (datetime.now(timezone.utc) + pd.Timedelta(minutes=LEASE_MINUTES)).isoformat()
    ids = [r["prediction_id"] for r in rows]
    supabase.table("user_predictions").update({"claimed_at": cutoff_iso, "lease_expires_at": new_lease}).in_(
        "prediction_id", ids
    ).execute()
    return rows
