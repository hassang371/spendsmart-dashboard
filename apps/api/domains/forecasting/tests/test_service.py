"""ForecastService tier-routing tests (RFC-003 §3 + LLD 009 Task 7).

These pin Stage 5's expanded contract: ``ForecastService.predict``
returns a fully-typed :class:`ForecastResponse` carrying 7-quantile
points, derived insights, and a ``prediction_id``. Cold-start users
(<90 days history) get Chronos-only; established users without a
trained model trigger Chronos with the established-user
confidence floor; users with both 90+ days AND a warm cache get the
ensemble path.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §3
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import numpy as np
import pandas as pd
import pytest

from apps.api.domains.forecasting.schemas import ForecastResponse


def _make_transactions(n_days: int = 100) -> pd.DataFrame:
    dates = pd.date_range("2025-10-01", periods=n_days, freq="D")
    rng = np.random.default_rng(42)
    amounts = rng.choice([-50.0, -20.0, 1000.0, -10.0], size=n_days)
    return pd.DataFrame({"date": dates, "amount": amounts})


def _stub_chronos_result(horizon: int = 30) -> dict:
    """Synthetic ChronosEngine.predict return."""
    forecast = []
    for i in range(horizon):
        forecast.append(
            {
                "date": (pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)).strftime("%Y-%m-%d"),
                "p2": 1000.0,
                "p10": 1100.0,
                "p25": 1200.0,
                "p50": 1300.0,
                "p75": 1400.0,
                "p90": 1500.0,
                "p98": 1600.0,
            }
        )
    return {
        "forecast": forecast,
        "model_type": "chronos2",
        "model_version": "chronos-2-small",
        "horizon": horizon,
    }


def _make_cache_mock(cached_model=None):
    """Build a TFTModelCache mock with an async ``get_or_load`` returning ``cached_model``."""
    cache = MagicMock()
    cache.get_or_load = AsyncMock(return_value=cached_model)
    return cache


def _make_supabase_mock():
    """Mock supabase client with .rpc() returning a MagicMock with .execute().data=True."""
    client = MagicMock()
    rpc_resp = MagicMock()
    rpc_resp.execute.return_value = MagicMock(data=True)
    client.rpc.return_value = rpc_resp
    return client


# ---------------------------------------------------------------------------
# Tier routing
# ---------------------------------------------------------------------------


def test_cold_start_uses_chronos():
    """<90 days history → Chronos-only; ``model_type`` = "chronos2"."""
    from apps.api.domains.forecasting.service import ForecastService

    short_df = _make_transactions(n_days=30)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(horizon=30)

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock())
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(short_df, user_id="user-cold", horizon=30)

    assert isinstance(result, ForecastResponse)
    assert result.model_type == "chronos2"
    assert result.confidence == "low"
    assert len(result.forecast) == 30
    assert result.variable_importance is None or result.variable_importance == []
    assert isinstance(result.prediction_id, UUID)


def test_established_user_without_model_falls_back_to_chronos():
    """>=90 days history but no warm cache entry → Chronos-only, confidence=medium."""
    from apps.api.domains.forecasting.service import ForecastService

    long_df = _make_transactions(n_days=120)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(horizon=30)

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock(cached_model=None))
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(long_df, user_id="user-warm-miss", horizon=30)

    assert result.model_type == "chronos2"
    assert result.confidence == "medium"


def test_warm_cache_runs_ensemble_path():
    """>=90 days + cache hit → ensemble path, model_type=ensemble, confidence=high."""
    from apps.api.domains.forecasting.service import ForecastService

    long_df = _make_transactions(n_days=120)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(horizon=30)

    cached = MagicMock()
    cached.model = MagicMock()
    cached.checkpoint_path = "ckpt/u1.ckpt"

    tft_result = _stub_chronos_result(horizon=30)
    tft_result["model_type"] = "tft_hybrid"
    tft_result["model_version"] = "tft_v1"

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock(cached_model=cached))
    with (
        patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos),
        patch("apps.api.domains.forecasting.service.predict_with_tft", return_value=tft_result),
        patch("apps.api.domains.forecasting.service.extract_variable_importance", return_value=None),
    ):
        result = svc.predict(long_df, user_id="user-warm-hit", horizon=30)

    assert result.model_type == "ensemble"
    assert result.confidence == "high"


def test_predict_returns_seven_quantile_points():
    """Each ForecastPoint must carry all seven quantiles (p2..p98)."""
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(n_days=50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(horizon=30)

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock())
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(df, user_id="user-q", horizon=30)

    point = result.forecast[0]
    for q in ("p2", "p10", "p25", "p50", "p75", "p90", "p98"):
        assert hasattr(point, q), f"ForecastPoint missing {q}"


def test_predict_attaches_insights_object():
    """Response.insights must be present even when compute_insights raises."""
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(n_days=50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(horizon=30)

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock())
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(df, user_id="user-i", horizon=30)

    assert result.insights is not None
    assert hasattr(result.insights, "safe_to_spend")


def test_predict_rejects_empty_dataframe():
    """Empty df → ValueError (router maps to 400)."""
    from apps.api.domains.forecasting.service import ForecastService

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock())
    with pytest.raises(ValueError):
        svc.predict(pd.DataFrame(columns=["date", "amount"]), user_id="x", horizon=30)


def test_predict_passes_filtered_intents_to_compute_insights():
    """LLD 010 — predict must filter active intents to LIFE_EVENT +
    (low | medium) confidence and pass them as ``active_intents`` to
    :func:`compute_insights`."""
    from datetime import date
    from uuid import uuid4

    from apps.api.domains.forecasting.schemas import (
        IntentConfidence,
        IntentType,
        UserIntent,
    )
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(n_days=50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(horizon=30)

    def _intent(intent_type, confidence, is_active=True) -> UserIntent:
        return UserIntent(
            id=uuid4(),
            user_id=uuid4(),
            intent_type=intent_type,
            amount=10000.0 if intent_type is not IntentType.LIFE_EVENT else None,
            amount_delta=None,
            category_bucket=None,
            start_date=date(2026, 5, 15),
            end_date=None,
            confidence=confidence,
            is_recurring=False,
            rrule_freq=None,
            notes=None,
            is_active=is_active,
            created_at="2026-04-17T00:00:00+00:00",
            updated_at="2026-04-17T00:00:00+00:00",
        )

    intents = [
        _intent(IntentType.LIFE_EVENT, IntentConfidence.HIGH),  # widens (LIFE_EVENT)
        _intent(IntentType.PLANNED_LARGE_EXPENSE, IntentConfidence.LOW),  # widens (low)
        _intent(IntentType.PLANNED_LARGE_EXPENSE, IntentConfidence.HIGH),  # NOT widened
        _intent(IntentType.LIFE_EVENT, IntentConfidence.MEDIUM, is_active=False),  # skipped
    ]

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock())
    svc._fetch_active_intents = MagicMock(return_value=intents)

    captured = {}

    def _capture(**kwargs):
        captured["active_intents"] = kwargs.get("active_intents")
        from apps.api.domains.forecasting.schemas import (
            ForecastInsights,
            LowestBalance,
            QuantileSnapshot,
        )

        return ForecastInsights(
            lowest_balance=LowestBalance(date="2026-01-01", p10=0.0, p50=0.0),
            month_end=QuantileSnapshot(p10=0.0, p50=0.0, p90=0.0),
            predicted_monthly_spend=0.0,
            predicted_monthly_income=0.0,
            confidence_band_width=0.0,
            primary_drivers=[],
            safe_to_spend=0.0,
            overdraft_risk_score=0.0,
            floor_used=0.0,
            floor_source="auto_p10_history",
        )

    with (
        patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos),
        patch("apps.api.domains.forecasting.service.compute_insights", side_effect=_capture),
    ):
        svc.predict(df, user_id="user-x", horizon=30)

    forwarded = captured["active_intents"]
    assert forwarded is not None
    types = {(i.intent_type, i.confidence) for i in forwarded}
    assert (IntentType.LIFE_EVENT, IntentConfidence.HIGH) in types
    assert (IntentType.PLANNED_LARGE_EXPENSE, IntentConfidence.LOW) in types
    # High-confidence non-LIFE_EVENT and inactive intents must be filtered out.
    assert (IntentType.PLANNED_LARGE_EXPENSE, IntentConfidence.HIGH) not in types
    assert all(i.is_active for i in forwarded)


def test_predict_with_no_intents_passes_none_to_compute_insights():
    """Backward-compat — users with zero intents see no change."""
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(n_days=50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(horizon=30)

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock())
    svc._fetch_active_intents = MagicMock(return_value=[])

    captured = {}

    def _capture(**kwargs):
        captured["active_intents"] = kwargs.get("active_intents")
        from apps.api.domains.forecasting.schemas import (
            ForecastInsights,
            LowestBalance,
            QuantileSnapshot,
        )

        return ForecastInsights(
            lowest_balance=LowestBalance(date="2026-01-01", p10=0.0, p50=0.0),
            month_end=QuantileSnapshot(p10=0.0, p50=0.0, p90=0.0),
            predicted_monthly_spend=0.0,
            predicted_monthly_income=0.0,
            confidence_band_width=0.0,
            primary_drivers=[],
            safe_to_spend=0.0,
            overdraft_risk_score=0.0,
            floor_used=0.0,
            floor_source="auto_p10_history",
        )

    with (
        patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos),
        patch("apps.api.domains.forecasting.service.compute_insights", side_effect=_capture),
    ):
        svc.predict(df, user_id="user-noi", horizon=30)

    assert captured["active_intents"] is None
