"""Unit tests for ``packages.forecasting.cache.TFTModelCache``.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §1
Refs: docs/bugs/BUG-018-tft-inference-cold-load-no-bounded-cache.md
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock

import pytest

from packages.forecasting.cache import CachedModel, TFTModelCache


def _make_entry(size_bytes: int = 1000, ts: Optional[datetime] = None) -> CachedModel:
    return CachedModel(
        model=MagicMock(),
        checkpoint_path=f"ckpt-{size_bytes}",
        checkpoint_updated_at=ts or datetime(2026, 1, 1, tzinfo=timezone.utc),
        size_bytes=size_bytes,
    )


def test_lru_evicts_oldest_when_max_entries_exceeded() -> None:
    cache = TFTModelCache(max_entries=2, max_bytes=10**12, ttl_seconds=10**9)
    cache._put("alice", _make_entry(100))
    cache._put("bob", _make_entry(100))
    # Insert third → oldest (alice) must evict.
    cache._put("carol", _make_entry(100))
    stats = cache.stats()
    assert stats.resident_entries == 2
    assert stats.evictions_lru == 1
    assert cache.peek("alice") is None
    assert cache.peek("bob") is not None
    assert cache.peek("carol") is not None


def test_byte_cap_evicts_oldest_when_total_exceeds_max_bytes() -> None:
    cache = TFTModelCache(max_entries=10, max_bytes=300, ttl_seconds=10**9)
    cache._put("alice", _make_entry(100))
    cache._put("bob", _make_entry(100))
    cache._put("carol", _make_entry(150))  # total=350 > 300 → evict oldest
    stats = cache.stats()
    assert stats.resident_bytes <= 300
    assert stats.evictions_bytes >= 1
    assert cache.peek("alice") is None


def test_ttl_eviction_advances_via_clock_seam() -> None:
    """Caching uses a monotonic clock seam; advance it past TTL and
    expect the next ``_get`` to evict the entry."""
    fake_now = [0.0]

    def fake_clock() -> float:
        return fake_now[0]

    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=60, clock=fake_clock)
    entry = _make_entry(100)
    entry.cached_at = fake_clock()
    cache._put("alice", entry)
    assert cache._get("alice") is not None
    fake_now[0] = 1000  # advance well past TTL
    assert cache._get("alice") is None
    stats = cache.stats()
    assert stats.evictions_ttl >= 1


def test_invalidate_evicts_entry() -> None:
    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9)
    cache._put("alice", _make_entry(100))
    assert cache.peek("alice") is not None
    cache.evict("alice", reason="invalidation")
    assert cache.peek("alice") is None
    stats = cache.stats()
    assert stats.evictions_invalidation == 1


def test_stats_reports_hits_and_misses() -> None:
    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9)
    cache._put("alice", _make_entry(100))
    assert cache._get("alice") is not None  # hit
    assert cache._get("missing") is None  # miss
    stats = cache.stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.resident_entries == 1


@pytest.mark.asyncio
async def test_get_or_load_calls_loader_on_miss_and_caches_result() -> None:
    calls = {"count": 0}

    def loader(user_id: str) -> Optional[CachedModel]:
        calls["count"] += 1
        return _make_entry(100)

    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9, loader=loader)
    first = await cache.get_or_load("alice")
    second = await cache.get_or_load("alice")
    assert first is not None
    assert first is second  # second call hits the cache
    assert calls["count"] == 1


@pytest.mark.asyncio
async def test_get_or_load_single_flight_serialises_concurrent_loads() -> None:
    """Two concurrent ``get_or_load`` for the same user_id must trigger
    exactly ONE underlying load. The follower awaits the leader's
    future."""

    import threading

    started = threading.Event()
    release = threading.Event()
    call_count = {"count": 0}

    def loader(user_id: str) -> Optional[CachedModel]:
        # Synchronous loader runs on a worker thread (asyncio.to_thread).
        # Signal that we have entered and block until released.
        call_count["count"] += 1
        started.set()
        release.wait(timeout=5.0)
        return _make_entry(123)

    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9, loader=loader)

    # Start the leader; wait until it is inside the loader on the worker
    # thread (so we know the inflight future is registered).
    leader = asyncio.create_task(cache.get_or_load("alice"))

    # Poll for ``started`` from the event loop without blocking it.
    for _ in range(50):
        if started.is_set():
            break
        await asyncio.sleep(0.01)
    assert started.is_set(), "leader never entered the loader"

    # Now spawn followers — they must NOT enter the loader because the
    # leader's future is already in _inflight.
    followers = [asyncio.create_task(cache.get_or_load("alice")) for _ in range(3)]
    # Yield so followers register on _inflight before we release the leader.
    for _ in range(5):
        await asyncio.sleep(0.01)

    release.set()
    leader_result = await leader
    follower_results = await asyncio.gather(*followers)

    assert leader_result is not None
    for r in follower_results:
        assert r is leader_result
    assert call_count["count"] == 1


@pytest.mark.asyncio
async def test_get_or_load_returns_none_when_loader_returns_none() -> None:
    def loader(user_id: str) -> Optional[CachedModel]:
        return None

    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9, loader=loader)
    result = await cache.get_or_load("nobody")
    assert result is None
    # Nothing should have been cached.
    assert cache.peek("nobody") is None


def test_put_replacing_existing_entry_decrements_resident_bytes() -> None:
    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9)
    cache._put("alice", _make_entry(100))
    cache._put("alice", _make_entry(50))
    stats = cache.stats()
    assert stats.resident_entries == 1
    assert stats.resident_bytes == 50
