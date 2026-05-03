"""Redis pub-sub channel for cross-worker TFT cache invalidation.

Per RFC-004 §Detailed Design 2: the polling worker publishes a message
to the ``CHANNEL`` whenever ``training_jobs.status`` transitions to
``completed``. Every API worker runs an asyncio subscriber that
receives the message, applies an out-of-order stale-guard, and evicts
the matching entry from its local ``TFTModelCache``.

The subscriber is intentionally async (``redis.asyncio``) rather than a
threaded subscriber so that:

* failures surface via the FastAPI lifespan logging,
* tests can drive it deterministically with ``fakeredis.aioredis``.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §2
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from apps.api.core.metrics import (
    tft_cache_pubsub_invalidations_skipped_stale_total,
    tft_cache_pubsub_invalidations_total,
    tft_cache_pubsub_publish_failures_total,
    tft_cache_subscriber_reconnects_total,
)
from packages.forecasting.cache import TFTModelCache

logger = logging.getLogger(__name__)

CHANNEL = "tft_cache_invalidation"


def _coerce_iso(value: Any) -> str:
    """Return a string ISO-8601 representation of ``value``."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _parse_iso(raw: str) -> datetime:
    """Parse an ISO-8601 string. ``Z`` suffix is normalised."""
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))


async def publish_invalidation(
    redis_client: Any,
    user_id: str,
    checkpoint_updated_at: Any,
) -> bool:
    """Publish a cache-invalidation message to ``CHANNEL``.

    Accepts either a sync or async ``redis_client`` — calls
    ``await redis_client.publish(...)`` and falls back to a synchronous
    call if the result is not awaitable.

    Returns ``True`` on success, ``False`` on any failure (failure is
    logged + counted via ``tft_cache_pubsub_publish_failures_total``).
    """
    payload = json.dumps(
        {
            "user_id": user_id,
            "checkpoint_updated_at": _coerce_iso(checkpoint_updated_at),
        }
    )
    try:
        result = redis_client.publish(CHANNEL, payload)
        if asyncio.iscoroutine(result):
            await result
        return True
    except Exception as exc:
        tft_cache_pubsub_publish_failures_total.inc()
        logger.warning(
            "cache_invalidation_publish_failed",
            extra={"user_id": user_id, "error": str(exc)},
        )
        return False


async def _handle_message(cache: TFTModelCache, raw: bytes | str) -> None:
    """Apply a single pub-sub message to ``cache``.

    Stale-guard: if the cached entry's ``checkpoint_updated_at`` is
    *newer* than the incoming payload's, skip the invalidation so an
    out-of-order delivery cannot evict a fresher model.
    """
    try:
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8")
        payload = json.loads(raw)
        user_id = payload["user_id"]
        incoming_ts = _parse_iso(payload["checkpoint_updated_at"])
    except Exception as exc:
        logger.error("cache_invalidation_dispatch_failed", extra={"error": str(exc)})
        return

    cached = cache.peek(user_id)
    if cached is not None:
        cached_ts = cached.checkpoint_updated_at
        if cached_ts.tzinfo is None:
            cached_ts = cached_ts.replace(tzinfo=timezone.utc)
        if incoming_ts.tzinfo is None:
            incoming_ts = incoming_ts.replace(tzinfo=timezone.utc)
        if incoming_ts <= cached_ts:
            tft_cache_pubsub_invalidations_skipped_stale_total.inc()
            logger.info(
                "cache_invalidation_skipped_stale_message",
                extra={"user_id": user_id},
            )
            return

    cache.evict(user_id, reason="invalidation")
    tft_cache_pubsub_invalidations_total.inc()
    logger.info("cache_invalidated_via_pubsub", extra={"user_id": user_id})


async def _subscriber_loop(
    redis_client: Any,
    cache: TFTModelCache,
    *,
    stop_event: Optional[asyncio.Event] = None,
    max_iterations: Optional[int] = None,
    backoff_initial: float = 1.0,
    backoff_max: float = 30.0,
) -> None:
    """Run the pub-sub subscribe loop until ``stop_event`` is set.

    The loop reconnects on any unexpected error, with exponential
    backoff (capped at ``backoff_max`` seconds). Each reconnect
    increments ``tft_cache_subscriber_reconnects_total``.

    ``max_iterations`` is a test-only guard: when set, the loop exits
    after that many reconnect cycles even if ``stop_event`` is unset.
    """
    backoff = backoff_initial
    iterations = 0
    first_pass = True
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        if max_iterations is not None and iterations >= max_iterations:
            return
        iterations += 1
        if not first_pass:
            tft_cache_subscriber_reconnects_total.inc()
        first_pass = False
        try:
            pubsub = redis_client.pubsub()
            subscribe_result = pubsub.subscribe(CHANNEL)
            if asyncio.iscoroutine(subscribe_result):
                await subscribe_result
            logger.info("tft_cache_subscriber_connected", extra={"channel": CHANNEL})
            backoff = backoff_initial
            try:
                while True:
                    if stop_event is not None and stop_event.is_set():
                        return
                    msg = await _next_message(pubsub)
                    if msg is None:
                        continue
                    if msg.get("type") != "message":
                        continue
                    await _handle_message(cache, msg.get("data"))
            finally:
                try:
                    close_result = pubsub.unsubscribe(CHANNEL)
                    if asyncio.iscoroutine(close_result):
                        await close_result
                except Exception:
                    pass
                try:
                    aclose = getattr(pubsub, "aclose", None) or getattr(pubsub, "close", None)
                    if aclose is not None:
                        result = aclose()
                        if asyncio.iscoroutine(result):
                            await result
                except Exception:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "tft_cache_subscriber_disconnected",
                extra={"error": str(exc), "backoff_s": backoff},
            )
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                raise
            backoff = min(backoff * 2, backoff_max)


async def _next_message(pubsub: Any) -> Optional[dict]:
    """Fetch the next pub-sub message regardless of client flavour.

    ``redis.asyncio`` exposes ``get_message(timeout=...)``. Some test
    fakes expose ``listen()`` as an async iterator — handle both.
    """
    get_message = getattr(pubsub, "get_message", None)
    if get_message is not None:
        try:
            msg = get_message(ignore_subscribe_messages=True, timeout=1.0)
        except TypeError:
            msg = get_message(timeout=1.0)
        if asyncio.iscoroutine(msg):
            msg = await msg
        return msg
    # Fallback: iterate listen() once.
    listen = pubsub.listen()
    if hasattr(listen, "__anext__"):
        return await listen.__anext__()  # type: ignore[no-any-return]
    return next(iter(listen), None)


def start_subscriber(
    redis_client: Any,
    cache: TFTModelCache,
    *,
    stop_event: Optional[asyncio.Event] = None,
) -> asyncio.Task:
    """Spawn the pub-sub subscriber as a background ``asyncio.Task``.

    Returns the task handle so the FastAPI lifespan can ``cancel()``
    it on shutdown.
    """
    return asyncio.create_task(
        _subscriber_loop(redis_client, cache, stop_event=stop_event),
        name="tft-cache-invalidator",
    )


def publish_invalidation_sync(
    redis_client: Any,
    user_id: str,
    checkpoint_updated_at: Any,
) -> bool:
    """Synchronous variant for the polling worker.

    The Celery / polling worker process is not running an asyncio event
    loop, so it uses ``redis.Redis`` (sync) instead of
    ``redis.asyncio``. Failure is non-fatal: logged + counted, never
    raised. The TTL fallback covers any missed message.
    """
    payload = json.dumps(
        {
            "user_id": user_id,
            "checkpoint_updated_at": _coerce_iso(checkpoint_updated_at),
        }
    )
    try:
        redis_client.publish(CHANNEL, payload)
        return True
    except Exception as exc:
        tft_cache_pubsub_publish_failures_total.inc()
        logger.warning(
            "cache_invalidation_publish_failed",
            extra={"user_id": user_id, "error": str(exc)},
        )
        return False


__all__ = [
    "CHANNEL",
    "publish_invalidation",
    "publish_invalidation_sync",
    "start_subscriber",
    "_subscriber_loop",
    "_handle_message",
]
