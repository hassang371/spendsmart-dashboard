"""ForecastService prediction-logging tests (RFC-003 §3 + §3b).

Pins:
* INSERT happens on first call per (user_id, hour) bucket.
* Concurrent calls under ``asyncio.gather`` produce exactly one
  inserted=true response from the RPC; the rest hit ON CONFLICT and
  return false (dedup-skipped).
* RPC failure → 200 still returned; ``prediction_id`` is a valid UUID;
  no exception escapes ``predict``.

Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §3, §3b
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch
from uuid import UUID

import numpy as np
import pandas as pd


def _make_transactions(n_days: int = 50) -> pd.DataFrame:
    dates = pd.date_range("2025-10-01", periods=n_days, freq="D")
    rng = np.random.default_rng(0)
    amounts = rng.choice([-50.0, 1000.0, -10.0], size=n_days)
    return pd.DataFrame({"date": dates, "amount": amounts})


def _stub_chronos_result(horizon: int = 30) -> dict:
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


def _make_supabase_mock(rpc_returns=True, rpc_raises=False):
    client = MagicMock()
    rpc_resp = MagicMock()
    if rpc_raises:
        rpc_resp.execute.side_effect = Exception("rpc failed")
    else:
        rpc_resp.execute.return_value = MagicMock(data=rpc_returns)
    client.rpc.return_value = rpc_resp
    return client


def _make_cache_mock(cached_model=None):
    from unittest.mock import AsyncMock

    cache = MagicMock()
    cache.get_or_load = AsyncMock(return_value=cached_model)
    return cache


# ---------------------------------------------------------------------------
# Logging — happy path
# ---------------------------------------------------------------------------


def test_predict_calls_log_user_prediction_rpc():
    """ForecastService.predict must invoke supabase.rpc('log_user_prediction', ...)."""
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(30)
    client = _make_supabase_mock(rpc_returns=True)

    svc = ForecastService(client, tft_cache=_make_cache_mock())
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(df, user_id="user-log", horizon=30)

    assert client.rpc.called, "log_user_prediction RPC was not invoked"
    call_args = client.rpc.call_args
    assert call_args[0][0] == "log_user_prediction"
    payload = call_args[0][1]["payload"]
    assert payload["user_id"] == "user-log"
    assert payload["horizon_days"] == 30
    assert payload["model_type"] == "chronos2"
    assert "prediction_id" in payload
    assert payload["prediction_id"] == str(result.prediction_id)
    assert payload["insights_version"] == "v1"
    assert "forecast" in payload
    assert "insights" in payload


def test_predict_returns_uuid_prediction_id():
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(30)

    svc = ForecastService(_make_supabase_mock(), tft_cache=_make_cache_mock())
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(df, user_id="u", horizon=30)

    assert isinstance(result.prediction_id, UUID)


# ---------------------------------------------------------------------------
# Failure tolerance — RPC raises
# ---------------------------------------------------------------------------


def test_predict_returns_200_when_rpc_raises():
    """RPC failure must NOT propagate; predict() returns a valid response."""
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(30)
    client = _make_supabase_mock(rpc_raises=True)

    svc = ForecastService(client, tft_cache=_make_cache_mock())
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(df, user_id="u", horizon=30)

    assert isinstance(result.prediction_id, UUID)
    assert result.model_type == "chronos2"


def test_predict_returns_uuid_when_rpc_raises():
    """Even on RPC failure, prediction_id must be a valid UUID."""
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(30)
    client = _make_supabase_mock(rpc_raises=True)

    svc = ForecastService(client, tft_cache=_make_cache_mock())
    with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
        result = svc.predict(df, user_id="u", horizon=30)

    assert isinstance(result.prediction_id, UUID)
    # Sanity-check: roundtrip via str
    assert UUID(str(result.prediction_id)) == result.prediction_id


# ---------------------------------------------------------------------------
# Concurrency — RFC-003 §3b atomic dedup
# ---------------------------------------------------------------------------


def test_concurrent_predict_does_not_duplicate():
    """N parallel predict() calls under asyncio.gather → RPC called N times,
    DB returns exactly ONE inserted=true and N-1 inserted=false (ON CONFLICT)."""
    from apps.api.domains.forecasting.service import ForecastService

    df = _make_transactions(50)
    chronos = MagicMock()
    chronos.predict.return_value = _stub_chronos_result(30)

    client = MagicMock()
    rpc_call_results: list[bool] = []

    def _rpc(name, body):
        # Simulate atomic UNIQUE behaviour: first call returns True, rest False.
        resp = MagicMock()

        def _execute():
            inserted = len(rpc_call_results) == 0
            rpc_call_results.append(inserted)
            return MagicMock(data=inserted)

        resp.execute.side_effect = _execute
        return resp

    client.rpc.side_effect = _rpc

    svc = ForecastService(client, tft_cache=_make_cache_mock())

    async def _run_one():
        await asyncio.sleep(0)  # release the loop so all coros race
        with patch("apps.api.domains.forecasting.service.get_chronos_engine", return_value=chronos):
            return svc.predict(df, user_id="user-concurrent", horizon=30)

    async def _gather():
        return await asyncio.gather(*[_run_one() for _ in range(5)])

    results = asyncio.run(_gather())

    assert len(results) == 5
    # Exactly one inserted=True; rest inserted=False
    assert sum(1 for r in rpc_call_results if r) == 1
    assert sum(1 for r in rpc_call_results if not r) == 4
    # All responses still carry valid UUIDs
    for r in results:
        assert isinstance(r.prediction_id, UUID)
