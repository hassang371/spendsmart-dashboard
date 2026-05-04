# BUG-024: TFTModelCache asyncio.Lock binds to subscriber loop, fails in worker thread

> **Doc ID:** BUG-024-tft-cache-async-lock-cross-loop
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Critical (TFT cache load fails on every request even after BUG-023 deadlock fix)

## Symptom

After BUG-023 was fixed (run `get_or_load` in a fresh-loop background thread), every predict logs:

```
tft_cache_load_failed user_id=... error="RuntimeError: Task <Task pending name='Task-25' coro=<TFTModelCache.get_or_load() running at .../packages/forecasting/cache.py:275> cb=[_run_until_complete_cb()...]> got Future <Future pending> attached to a different loop"
```

TFT model never reaches the cache; ensemble path never engages.

## Root cause

`TFTModelCache.__init__` constructs `self._inflight_lock = asyncio.Lock()`. In CPython 3.10+ `asyncio.Lock` defers loop binding until first `acquire()`.

The pub-sub subscriber spawned by the FastAPI lifespan (`tft_cache_subscriber_started`) runs on the **FastAPI serving loop** and performs a `peek` / `evict` cycle that does *not* touch `_inflight_lock`, but a different earlier path (cache stats endpoint or test seam) acquires the lock first inside the FastAPI loop. The lock is now bound to that loop.

When `_safe_get_cached_model` (BUG-023 fix) runs `asyncio.run(get_or_load(...))` inside a daemon thread, a **new loop** is created. `get_or_load` calls `async with self._inflight_lock` — but the lock is bound to the FastAPI loop, so the new loop's task references a `Future` from the wrong loop, and CPython raises:

> got Future <Future pending> attached to a different loop

The shared `asyncio.Lock` cannot bridge two loops. Single-flight via `asyncio.Lock` is fundamentally incompatible with the "fresh loop per call" pattern BUG-023 introduced.

## Fix

Stop using the async path from the request handler entirely. The cache's *internal* state (`_get`, `_put`, `_download_and_load`) is already protected by a `threading.RLock` and is loop-agnostic. Bypass `get_or_load` and call those primitives directly from a new sync helper:

```python
def get_or_load_sync(self, user_id: str) -> Optional[CachedModel]:
    cached = self._get(user_id)
    if cached is not None:
        return cached
    result = self._download_and_load(user_id)
    if result is not None:
        self._put(user_id, result)
    return result
```

`_safe_get_cached_model` calls `cache.get_or_load_sync(user_id)` inside a daemon thread (so a slow checkpoint download cannot block the serving loop). No event loop, no `asyncio.Lock`, no cross-loop futures.

Trade-off: we lose `asyncio.Lock`-based single-flight. For SCALE's single-user prod that costs at most one duplicate checkpoint download on a cold start race; worth the simplicity. A future revision can add `threading.Lock`-based single-flight if profiling shows redundant loads in multi-user prod.

The async `get_or_load` is preserved for tests and any future async caller, but production traffic no longer touches it.

## Regression prevention

- Add an integration test that drives `get_or_load_sync` from inside a fresh thread, asserting it returns the cached model and that the cache's `_resident_bytes` increases.
- Add a smoke assertion in `_safe_get_cached_model` that the resolved model is non-None on the second call (warm-cache hit), failing loudly if the cache silently misses.

## Refs

- `packages/forecasting/cache.py::TFTModelCache.get_or_load`
- `apps/api/domains/forecasting/service.py::_safe_get_cached_model`
- BUG-023 (predecessor: self-loop deadlock)
- RFC-004 §Detailed Design 1
