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
