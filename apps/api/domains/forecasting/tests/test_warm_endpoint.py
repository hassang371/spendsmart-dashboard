"""Tests for ``POST /api/v1/forecast/warm``.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §3
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from apps.api.core.auth import (
    CurrentUser,
    get_current_user,
    get_current_user_id,
    get_user_client,
)
from apps.api.domains.forecasting.router import _get_tft_cache
from apps.api.main import app
from packages.forecasting.cache import CachedModel


def _make_cached() -> CachedModel:
    return CachedModel(
        model=MagicMock(),
        checkpoint_path="ckpt",
        checkpoint_updated_at=datetime(2026, 4, 18, tzinfo=timezone.utc),
        size_bytes=1000,
    )


def _setup_overrides(mock_cache: MagicMock) -> None:
    app.dependency_overrides[_get_tft_cache] = lambda: mock_cache
    app.dependency_overrides[get_current_user_id] = lambda: "test-user-id"
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id="test-user-id", email=None)
    app.dependency_overrides[get_user_client] = lambda: MagicMock()


def test_warm_returns_ready_when_load_completes_in_window():
    mock_cache = MagicMock()

    async def _ok_load(user_id: str):
        return _make_cached()

    mock_cache.get_or_load = _ok_load

    _setup_overrides(mock_cache)
    try:
        with TestClient(app) as tc:
            # Disable rate-limit AFTER lifespan has run.
            app.state.warm_rate_limiter = None
            resp = tc.post("/api/v1/forecast/warm")
            assert resp.status_code == 202
            body = resp.json()
            assert body["status"] == "ready"
            assert body["user_id"] == "test-user-id"
    finally:
        app.dependency_overrides.clear()


def test_warm_returns_warming_when_load_exceeds_timeout():
    """If the cache load takes longer than the bounded window, the
    endpoint must return ``status="warming"`` instead of blocking."""
    mock_cache = MagicMock()

    async def _slow_load(user_id: str):
        await asyncio.sleep(2.0)
        return _make_cached()

    mock_cache.get_or_load = _slow_load

    _setup_overrides(mock_cache)
    try:
        with TestClient(app) as tc:
            app.state.warm_rate_limiter = None
            from apps.api.domains.forecasting import router as fr_router

            old = fr_router.WARM_BOUNDED_TIMEOUT_SECONDS
            fr_router.WARM_BOUNDED_TIMEOUT_SECONDS = 0.05
            try:
                resp = tc.post("/api/v1/forecast/warm")
            finally:
                fr_router.WARM_BOUNDED_TIMEOUT_SECONDS = old

            assert resp.status_code == 202
            assert resp.json()["status"] == "warming"
    finally:
        app.dependency_overrides.clear()


def test_warm_returns_failed_when_loader_returns_none():
    mock_cache = MagicMock()

    async def _none_load(user_id: str):
        return None

    mock_cache.get_or_load = _none_load

    _setup_overrides(mock_cache)
    try:
        with TestClient(app) as tc:
            app.state.warm_rate_limiter = None
            resp = tc.post("/api/v1/forecast/warm")
            assert resp.status_code == 202
            assert resp.json()["status"] == "failed"
    finally:
        app.dependency_overrides.clear()


def test_warm_requires_authentication():
    """Without a Bearer token, the endpoint must reject with 401."""
    # No auth override here — let the real get_current_user run.
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(get_current_user, None)
    with TestClient(app) as tc:
        app.state.warm_rate_limiter = None
        resp = tc.post("/api/v1/forecast/warm")
    assert resp.status_code == 401
