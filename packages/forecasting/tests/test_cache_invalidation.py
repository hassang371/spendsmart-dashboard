"""Unit tests for ``packages.forecasting.cache_invalidation``.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §2
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock

import fakeredis.aioredis
import pytest

from apps.api.core.metrics import (
    tft_cache_pubsub_invalidations_skipped_stale_total,
    tft_cache_pubsub_invalidations_total,
    tft_cache_pubsub_publish_failures_total,
    tft_cache_subscriber_reconnects_total,
)
from packages.forecasting.cache import CachedModel, TFTModelCache
from packages.forecasting.cache_invalidation import (
    CHANNEL,
    _handle_message,
    _subscriber_loop,
    publish_invalidation,
)


def _entry_with_ts(ts: datetime, size_bytes: int = 100) -> CachedModel:
    return CachedModel(
        model=MagicMock(),
        checkpoint_path="ckpt",
        checkpoint_updated_at=ts,
        size_bytes=size_bytes,
    )


def _counter_value(counter: Any, **labels: str) -> float:
    """Read a Prometheus Counter sample value scoped to the optional labels."""
    if labels:
        return counter.labels(**labels)._value.get()
    return counter._value.get()


@pytest.mark.asyncio
async def test_publish_invalidation_publishes_to_channel() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    # Drain the subscribe-confirmation message.
    await pubsub.get_message(timeout=1.0)

    ts = datetime(2026, 4, 18, 12, tzinfo=timezone.utc)
    ok = await publish_invalidation(redis, "alice", ts)
    assert ok is True

    # Wait for the message to arrive on the subscriber.
    msg = None
    for _ in range(20):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if msg is not None:
            break
    assert msg is not None
    payload = json.loads(msg["data"])
    assert payload["user_id"] == "alice"
    assert payload["checkpoint_updated_at"].startswith("2026-04-18")

    await pubsub.unsubscribe(CHANNEL)
    await pubsub.aclose()
    await redis.aclose()


@pytest.mark.asyncio
async def test_publish_invalidation_failure_increments_counter() -> None:
    bad_client = MagicMock()
    bad_client.publish = MagicMock(side_effect=RuntimeError("boom"))
    before = _counter_value(tft_cache_pubsub_publish_failures_total)
    ok = await publish_invalidation(bad_client, "alice", "2026-04-18T12:00:00Z")
    assert ok is False
    after = _counter_value(tft_cache_pubsub_publish_failures_total)
    assert after - before == 1.0


@pytest.mark.asyncio
async def test_handle_message_evicts_when_incoming_is_newer() -> None:
    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9)
    old_ts = datetime(2026, 4, 1, tzinfo=timezone.utc)
    cache._put("alice", _entry_with_ts(old_ts))

    new_ts = old_ts + timedelta(hours=1)
    payload = json.dumps({"user_id": "alice", "checkpoint_updated_at": new_ts.isoformat()})
    before = _counter_value(tft_cache_pubsub_invalidations_total)
    await _handle_message(cache, payload)
    after = _counter_value(tft_cache_pubsub_invalidations_total)

    assert cache.peek("alice") is None
    assert after - before == 1.0


@pytest.mark.asyncio
async def test_handle_message_skips_when_incoming_is_stale() -> None:
    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9)
    new_ts = datetime(2026, 4, 18, tzinfo=timezone.utc)
    cache._put("alice", _entry_with_ts(new_ts))

    stale_ts = new_ts - timedelta(hours=1)
    payload = json.dumps({"user_id": "alice", "checkpoint_updated_at": stale_ts.isoformat()})
    before_skip = _counter_value(tft_cache_pubsub_invalidations_skipped_stale_total)
    before_ok = _counter_value(tft_cache_pubsub_invalidations_total)
    await _handle_message(cache, payload)
    after_skip = _counter_value(tft_cache_pubsub_invalidations_skipped_stale_total)
    after_ok = _counter_value(tft_cache_pubsub_invalidations_total)

    # Entry must remain because the incoming message is stale.
    assert cache.peek("alice") is not None
    assert after_skip - before_skip == 1.0
    assert after_ok == before_ok


@pytest.mark.asyncio
async def test_subscriber_receives_published_message_and_evicts() -> None:
    redis = fakeredis.aioredis.FakeRedis()
    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9)
    old_ts = datetime(2026, 4, 1, tzinfo=timezone.utc)
    cache._put("alice", _entry_with_ts(old_ts))

    stop_event = asyncio.Event()
    task = asyncio.create_task(_subscriber_loop(redis, cache, stop_event=stop_event))
    # Wait briefly for the subscriber to register.
    await asyncio.sleep(0.05)

    new_ts = old_ts + timedelta(hours=2)
    await publish_invalidation(redis, "alice", new_ts)

    # Wait for eviction (poll up to 1 s).
    for _ in range(50):
        if cache.peek("alice") is None:
            break
        await asyncio.sleep(0.02)

    assert cache.peek("alice") is None

    stop_event.set()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass
    await redis.aclose()


@pytest.mark.asyncio
async def test_subscriber_reconnects_after_disconnect() -> None:
    """When ``pubsub.subscribe`` raises, the loop must back off and
    retry, incrementing ``tft_cache_subscriber_reconnects_total`` on
    each reconnect."""

    cache = TFTModelCache(max_entries=10, max_bytes=10**12, ttl_seconds=10**9)
    failures = {"count": 0}

    class FlakyPubSub:
        def subscribe(self, channel: str) -> None:
            failures["count"] += 1
            raise RuntimeError("connection reset")

    class FlakyClient:
        def pubsub(self) -> FlakyPubSub:
            return FlakyPubSub()

    before = _counter_value(tft_cache_subscriber_reconnects_total)
    # Run two iterations, each fails -> 1 reconnect counter increment
    # (the first iteration is the initial connect, not a reconnect).
    await _subscriber_loop(
        FlakyClient(),
        cache,
        max_iterations=2,
        backoff_initial=0.01,
        backoff_max=0.01,
    )
    after = _counter_value(tft_cache_subscriber_reconnects_total)

    assert failures["count"] == 2
    assert after - before == 1.0
