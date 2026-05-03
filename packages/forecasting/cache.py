"""Bounded LRU cache of per-user TFT models.

Replaces the unbounded module-level dict in ``inference.py`` per BUG-018.
See RFC-004 §Detailed Design 1 for the authoritative spec.

Key properties:

* **Bounded.** Hard caps on both entry count and total resident bytes;
  oldest-first eviction enforces both.
* **TTL fallback.** Each entry expires after ``ttl_seconds`` so that a
  missed pub-sub invalidation only leaves stale state for a bounded
  window.
* **Single-flight.** Concurrent ``get_or_load(user_id)`` callers for the
  same user share one ``asyncio.Future``; only the *leader* coroutine
  runs ``_download_and_load`` via ``asyncio.to_thread``. Followers
  ``await`` the leader's future.
* **Async-only public surface.** The public load contract is
  ``await cache.get_or_load(user_id)``. Internal mutators (``put``,
  ``evict``, ``stats``) hold a ``threading.RLock`` so synchronous helpers
  inside ``asyncio.to_thread`` are safe.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §1
Refs: docs/bugs/BUG-018-tft-inference-cold-load-no-bounded-cache.md
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import sys
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from time import monotonic
from typing import Any, Callable, Optional

from apps.api.core.metrics import (
    tft_cache_evictions_total,
    tft_cache_hits_total,
    tft_cache_load_duration_seconds,
    tft_cache_misses_total,
    tft_cache_resident_bytes,
    tft_cache_resident_entries,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default config — read from environment with sensible fallbacks. Per the
# Stage 3 deliverable: TFT_CACHE_MAX_ENTRIES (64), TFT_CACHE_MAX_BYTES (2 GB),
# TFT_CACHE_TTL_SECONDS (3600).
# ---------------------------------------------------------------------------
def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid_int_env", name=name, value=raw, default=default)
        return default


DEFAULT_MAX_ENTRIES = _env_int("TFT_CACHE_MAX_ENTRIES", 64)
DEFAULT_MAX_BYTES = _env_int("TFT_CACHE_MAX_BYTES", 2_000_000_000)
DEFAULT_TTL_SECONDS = _env_int("TFT_CACHE_TTL_SECONDS", 3600)


@dataclass
class CachedModel:
    """One entry in the cache.

    ``model``: the loaded ``TemporalFusionTransformer`` instance (or any
    object — typing kept loose so tests can substitute a sentinel
    without importing the real class).

    ``checkpoint_updated_at``: the ``training_jobs.updated_at`` value at
    load time. Used by the pub-sub subscriber as a stale-guard so an
    out-of-order invalidation message cannot evict a *newer* entry.
    """

    model: Any
    checkpoint_path: str
    checkpoint_updated_at: datetime
    size_bytes: int
    last_access: float = field(default_factory=monotonic)
    cached_at: float = field(default_factory=monotonic)
    hit_count: int = 0


@dataclass
class CacheStats:
    """Snapshot of cache counters."""

    hits: int
    misses: int
    evictions_lru: int
    evictions_bytes: int
    evictions_ttl: int
    evictions_invalidation: int
    resident_entries: int
    resident_bytes: int


class TFTModelCache:
    """Thread-safe bounded LRU+TTL+byte-cap cache with single-flight loads."""

    def __init__(
        self,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_bytes: int = DEFAULT_MAX_BYTES,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        loader: Optional[Callable[[str], Optional[CachedModel]]] = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._entries: "OrderedDict[str, CachedModel]" = OrderedDict()
        self._lock = threading.RLock()
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._ttl = ttl_seconds
        self._resident_bytes = 0
        # Counters
        self.hits = 0
        self.misses = 0
        self.evictions_lru = 0
        self.evictions_bytes = 0
        self.evictions_ttl = 0
        self.evictions_invalidation = 0
        # Single-flight state — keyed by user_id, holds the in-progress
        # load future. Cleared in the leader's ``finally`` block.
        self._inflight: dict[str, asyncio.Future[Optional[CachedModel]]] = {}
        self._inflight_lock = asyncio.Lock()
        # Test seam: pluggable loader. Production wiring sets this to a
        # callable closing over the Supabase client.
        self._loader: Optional[Callable[[str], Optional[CachedModel]]] = loader
        self._clock = clock

    # ------------------------------------------------------------------ #
    # Sync surface (safe to call from inside ``asyncio.to_thread``).
    # ------------------------------------------------------------------ #

    def _get(self, user_id: str) -> Optional[CachedModel]:
        """Internal lookup. Returns ``None`` on miss OR on TTL eviction."""
        with self._lock:
            entry = self._entries.get(user_id)
            if entry is None:
                self.misses += 1
                tft_cache_misses_total.inc()
                return None
            # TTL check
            if self._clock() - entry.cached_at > self._ttl:
                self._evict_unlocked(user_id, reason="ttl")
                self.misses += 1
                tft_cache_misses_total.inc()
                return None
            self._entries.move_to_end(user_id)  # mark as recently used
            entry.last_access = self._clock()
            entry.hit_count += 1
            self.hits += 1
            tft_cache_hits_total.inc()
            return entry

    def _put(self, user_id: str, cached: CachedModel) -> None:
        with self._lock:
            existing = self._entries.pop(user_id, None)
            if existing is not None:
                self._resident_bytes -= existing.size_bytes
            self._entries[user_id] = cached
            self._resident_bytes += cached.size_bytes
            self._evict_lru()
            self._refresh_gauges_unlocked()

    def evict(self, user_id: str, reason: str = "invalidation") -> None:
        """Evict ``user_id`` from the cache, attributing the eviction to
        ``reason`` (``lru`` | ``bytes`` | ``ttl`` | ``invalidation``)."""
        with self._lock:
            self._evict_unlocked(user_id, reason=reason)
            self._refresh_gauges_unlocked()

    def stats(self) -> CacheStats:
        with self._lock:
            return CacheStats(
                hits=self.hits,
                misses=self.misses,
                evictions_lru=self.evictions_lru,
                evictions_bytes=self.evictions_bytes,
                evictions_ttl=self.evictions_ttl,
                evictions_invalidation=self.evictions_invalidation,
                resident_entries=len(self._entries),
                resident_bytes=self._resident_bytes,
            )

    def peek(self, user_id: str) -> Optional[CachedModel]:
        """Non-promoting, non-locking peek. Used by the pub-sub
        subscriber's stale-guard which compares incoming
        ``checkpoint_updated_at`` against the resident entry's."""
        return self._entries.get(user_id)

    # ------------------------------------------------------------------ #
    # Eviction internals (caller already holds ``self._lock``).
    # ------------------------------------------------------------------ #

    def _evict_lru(self) -> None:
        """Enforce both entry-count and byte caps. Oldest-first."""
        while len(self._entries) > self._max_entries or self._resident_bytes > self._max_bytes:
            user_id, _ = next(iter(self._entries.items()))
            reason = (
                "bytes" if self._resident_bytes > self._max_bytes and len(self._entries) <= self._max_entries else "lru"
            )
            self._evict_unlocked(user_id, reason=reason)

    def _evict_unlocked(self, user_id: str, *, reason: str) -> None:
        entry = self._entries.pop(user_id, None)
        if entry is None:
            return
        self._resident_bytes -= entry.size_bytes
        if reason == "lru":
            self.evictions_lru += 1
        elif reason == "bytes":
            self.evictions_bytes += 1
        elif reason == "ttl":
            self.evictions_ttl += 1
        elif reason == "invalidation":
            self.evictions_invalidation += 1
        tft_cache_evictions_total.labels(reason=reason).inc()

    def _refresh_gauges_unlocked(self) -> None:
        tft_cache_resident_entries.set(len(self._entries))
        tft_cache_resident_bytes.set(self._resident_bytes)

    # ------------------------------------------------------------------ #
    # Async public surface.
    # ------------------------------------------------------------------ #

    async def get_or_load(self, user_id: str) -> Optional[CachedModel]:
        """Single-flight async load. Returns the cached entry on hit,
        triggers exactly one ``_download_and_load`` on miss, and
        broadcasts the result to all coroutines awaiting the same user.
        """
        cached = self._get(user_id)
        if cached is not None:
            return cached

        async with self._inflight_lock:
            fut = self._inflight.get(user_id)
            if fut is None:
                fut = asyncio.get_running_loop().create_future()
                self._inflight[user_id] = fut
                leader = True
            else:
                leader = False

        if leader:
            start = monotonic()
            try:
                result = await asyncio.to_thread(self._download_and_load, user_id)
                if result is not None:
                    self._put(user_id, result)
                if not fut.done():
                    fut.set_result(result)
                tft_cache_load_duration_seconds.observe(monotonic() - start)
                return result
            except Exception as exc:
                if not fut.done():
                    fut.set_exception(exc)
                raise
            finally:
                async with self._inflight_lock:
                    self._inflight.pop(user_id, None)

        return await fut

    # ------------------------------------------------------------------ #
    # Loader. Default implementation calls a registered ``self._loader``
    # callable; tests typically pass an ``AsyncMock`` or ``MagicMock``
    # via the ``loader=`` constructor kwarg, while production wires it
    # to ``functools.partial(_default_download_and_load, supabase)``.
    # ------------------------------------------------------------------ #

    def _download_and_load(self, user_id: str) -> Optional[CachedModel]:
        """Synchronous loader. Runs inside ``asyncio.to_thread``.

        If a custom ``loader`` was supplied at construction it is
        invoked here; otherwise this method is a stub that returns
        ``None`` and logs a warning. In production the FastAPI lifespan
        hook injects a real loader bound to the Supabase service-role
        client.
        """
        if self._loader is not None:
            return self._loader(user_id)
        logger.warning("tft_cache_loader_not_configured", user_id=user_id)
        return None

    def set_loader(self, loader: Callable[[str], Optional[CachedModel]]) -> None:
        """Install or replace the loader callable. Used by the FastAPI
        lifespan to inject a Supabase-backed loader after construction.
        """
        self._loader = loader


# ---------------------------------------------------------------------------
# Default supabase-backed loader. Imported lazily so the module's import
# graph stays decoupled from heavy ML deps in unit tests.
# ---------------------------------------------------------------------------


def default_supabase_loader(supabase: Any, user_id: str) -> Optional[CachedModel]:
    """Production loader. Wrap with ``functools.partial(supabase=...)``
    and pass the result to ``cache.set_loader``.

    Returns ``None`` on any recoverable failure so the caller can fall
    back to the Chronos-only path.
    """
    try:
        resp = (
            supabase.table("training_jobs")
            .select("checkpoint_path, updated_at")
            .eq("user_id", user_id)
            .eq("status", "completed")
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
    except Exception as exc:
        logger.error("load_job_fetch_failed", extra={"user_id": user_id, "error": str(exc)})
        return None

    if not resp.data:
        logger.info("no_trained_model", extra={"user_id": user_id})
        return None

    row = resp.data[0]
    checkpoint_path: str = row["checkpoint_path"]
    updated_at_raw: str = row.get("updated_at") or ""
    try:
        checkpoint_updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
    except Exception:
        checkpoint_updated_at = datetime.now(timezone.utc)

    try:
        buf = supabase.storage.from_("model-checkpoints").download(checkpoint_path)
    except Exception as exc:
        logger.error(
            "checkpoint_download_failed",
            extra={"checkpoint_path": checkpoint_path, "error": str(exc)},
        )
        return None

    try:
        from pytorch_forecasting import TemporalFusionTransformer  # local import

        with io.BytesIO(buf) as bio:
            model = TemporalFusionTransformer.load_from_checkpoint(bio, map_location="cpu")
            model.eval()
            model.freeze()
    except Exception as exc:
        logger.error(
            "checkpoint_deserialize_failed",
            extra={"checkpoint_path": checkpoint_path, "error": str(exc)},
        )
        return None

    try:
        param_bytes = sum(p.numel() for p in model.parameters()) * 4
        buffer_bytes = sum(b.numel() for b in model.buffers()) * 4
        size_bytes = param_bytes + buffer_bytes + sys.getsizeof(buf)
    except Exception:
        size_bytes = sys.getsizeof(buf)

    return CachedModel(
        model=model,
        checkpoint_path=checkpoint_path,
        checkpoint_updated_at=checkpoint_updated_at,
        size_bytes=size_bytes,
    )


__all__ = [
    "CachedModel",
    "CacheStats",
    "TFTModelCache",
    "default_supabase_loader",
    "DEFAULT_MAX_ENTRIES",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TTL_SECONDS",
]
