# BUG-023: TFT cache load deadlocks against its own event loop

> **Doc ID:** BUG-023-tft-cache-self-loop-deadlock
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Critical (TFT never serves predictions; ensemble degrades to Chronos-only forever)

## Symptom

Every `/forecast/predict` call logs:

```
tft_cache_load_failed user_id=... error=
Loading Chronos model: amazon/chronos-bolt-small
```

`error=` is empty (no exception message). Each predict round-trip takes ~30 seconds. Frontend always shows Chronos tier on first paint after tab refocus — TFT never takes over even though `training_jobs` has `status='completed'` and the checkpoint downloads with HTTP 200 OK.

## Root cause

`forecast_predict_get` (and POST sibling) are `async def` FastAPI handlers. They call `service.predict(...)` synchronously, which calls `_safe_get_cached_model(user_id)` synchronously. Inside that helper:

```python
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = None

if loop is not None and loop.is_running():
    future = asyncio.run_coroutine_threadsafe(self.tft_cache.get_or_load(user_id), loop)
    return future.result(timeout=30)
```

`asyncio.get_running_loop()` succeeds and returns FastAPI's serving loop. We then schedule the coroutine onto **that same loop** and synchronously block (`future.result(timeout=30)`) on the result. The loop cannot advance the scheduled coroutine because the only thread driving it is the one we just blocked → guaranteed deadlock.

After 30 seconds, `concurrent.futures.TimeoutError()` is raised. `str(TimeoutError())` is the empty string, which is exactly what the log shows (`error=`).

Consequences:
- TFT cache `_put` is never reached → cache stays empty
- Every predict eats 30s of wasted wall time before falling back to Chronos
- Ensemble path (RFC-003) is never exercised in production
- Auto-enqueue still detects `status='completed'` row but the downstream cache load can never succeed

## Fix

Run the async `get_or_load` on a **fresh event loop in a background thread** so it cannot collide with the FastAPI serving loop. `_safe_get_cached_model` becomes:

```python
import threading

result_box: list[Any] = [None]
err_box: list[BaseException | None] = [None]

def _runner() -> None:
    try:
        result_box[0] = asyncio.run(self.tft_cache.get_or_load(user_id))
    except BaseException as exc:  # noqa: BLE001
        err_box[0] = exc

t = threading.Thread(target=_runner, name=f"tft-cache-load:{user_id}", daemon=True)
t.start()
t.join(timeout=60)

if t.is_alive():
    logger.warning("tft_cache_load_timeout", user_id=user_id)
    return None
if err_box[0] is not None:
    logger.warning(
        "tft_cache_load_failed",
        user_id=user_id,
        error=f"{type(err_box[0]).__name__}: {err_box[0]}",
    )
    return None
return result_box[0]
```

Notes:
- `asyncio.run` inside the worker thread creates and tears down its own loop — no conflict with the FastAPI loop.
- Error log now includes the exception type (`TimeoutError:`) so future failures are diagnosable even when `str(exc)` is empty.
- 60s join timeout >> the 30s loader inner timeout so we never see false-positive cache-load timeouts when the loader is genuinely slow on cold start.

## Regression prevention

- Add an integration test that drives `/forecast/predict` with a real (mocked) cached `TemporalFusionTransformer` and asserts the response carries `model_type=ensemble`, not `chronos`.
- Add an assertion to `_safe_get_cached_model` that the error log is non-empty when failure occurs (diagnostic safeguard).

## Refs

- `apps/api/domains/forecasting/service.py::_safe_get_cached_model`
- `packages/forecasting/cache.py::TFTModelCache.get_or_load`
- RFC-004 §Detailed Design 1
