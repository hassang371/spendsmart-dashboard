# BUG-031: Worker poll spam, duplicate cold-load checkpoint downloads, and Lightning log noise

> **Doc ID:** BUG-031-worker-poll-spam-cache-double-load-and-log-noise
> **Date:** 2026-05-04
> **Status:** Fix Applied
> **Severity:** Medium (operational hygiene — every minute of cost wasted on poll requests + duplicate downloads + readability)

## Symptoms

1. Worker log emits one `GET /training_jobs?status=pending` every ~5 seconds even when no jobs are queued. Hours of idle = thousands of requests against the Supabase REST budget.
2. Backend log shows TWO `GET .../tft_best.ckpt` storage requests on every cold-cache `/forecast/predict`. Each download is ~20MB and takes ~3s; doubling that on cold start is wasted bandwidth.
3. Backend log floods with Lightning's per-predict banners (`GPU available: True`, `TPU available`, "Tip: install litlogger…", tensorboardX-removed notice) plus Chronos-Bolt's quantile-clamp warning, drowning the actual signal.

## Root causes

### 1. Polling-only worker

The worker's main loop ended in `time.sleep(5)` whenever no job was found. No push channel, no NOTIFY/LISTEN. Every 5s the worker hits the REST API regardless of whether anything happened.

### 2. Sync cache path lost single-flight in BUG-024

The original `TFTModelCache.get_or_load` used `asyncio.Lock` for single-flight. BUG-024 (asyncio.Lock cross-loop binding) forced us to switch the production path to `get_or_load_sync`, but the BUG-024 fix DROPPED single-flight as a deliberate trade-off. Two near-simultaneous predict requests therefore each invoke the loader → two concurrent checkpoint downloads → two `GET tft_best.ckpt` lines.

The trade-off was acceptable for "at most one duplicate download on a cold-start race", but Hassan's `/forecast/warm` + `/forecast/predict` fire in parallel from the page load, hitting the race window every time.

### 3. Lightning + Chronos warnings not all silenced

`apps/worker/main.py` filtered the per-batch sklearn StandardScaler noise (BUG-019/-028) but left:
- Lightning `lightning.pytorch` logger emitting INFO banners (`GPU available: True`, `TPU available: False`, "Tip: ...", tensorboardX notice) once per `Trainer()` construction. The predict path in `extract_variable_importance` builds a fresh trainer every call.
- Chronos-Bolt's quantile-clamp UserWarning (`Quantiles to be predicted ([0.02, 0.1, ...]) are not within the range of quantiles that Chronos-Bolt was trained on...`) — fixed-text, per-predict, expected behaviour per BUG-026 residue.
- `httpx` INFO-level access logs printing every Supabase REST call (poll GETs, scheduled_cashflows duplicate-key 409s that the worker intentionally swallows per BUG-022).

## Fixes

### Fix 1 — Push-based worker via Supabase Realtime + 30s poll fallback

Worker spawns a daemon thread running an `AsyncRealtimeClient` subscribed to `INSERT` on `public.training_jobs`. Each event sets a `threading.Event`. Main loop blocks on `event.wait(timeout=30)` instead of `time.sleep(5)`. Effect:

- Job arrives → frontend INSERT → Realtime push → event set → worker picks up within ~50ms (vs up to 5s before).
- No jobs → worker sleeps 30s instead of 5s. 6× fewer poll requests at idle.
- Realtime websocket blip → fallback poll still runs every 30s; nothing strands.

The `is_connected` check + outer reconnect loop handles transient websocket drops.

### Fix 2 — Per-user `threading.Lock` single-flight on `get_or_load_sync`

Rebuild single-flight on `threading.Lock` (loop-agnostic, immune to BUG-024). Two concurrent same-user loads:

```
Thread A: acquire user_lock['90a4...'] → cache miss → download (~3s) → put → release
Thread B: acquire user_lock['90a4...'] → cache hit (recheck) → return
```

One download. Frontend cold-path drops from 6s/40MB to 3s/20MB.

### Fix 3 — Quiet the noisy loggers

- `logging.getLogger("lightning.pytorch").setLevel(WARNING)` + same for `pytorch_lightning` — silences INFO banners, real warnings still surface.
- `logging.getLogger("httpx").setLevel(WARNING)` (worker) — drops the per-poll GET access log lines and the intentional 409s on `scheduled_cashflows`.
- `warnings.filterwarnings(... message="Quantiles to be predicted", category=UserWarning)` (api + worker) — silences the Chronos clamp warning.

Net effect: backend predict log goes from ~120 lines to ~10 lines per request.

## Regression prevention

- Add an integration test that asserts only one storage GET fires when two parallel `_safe_get_cached_model` calls hit the same cold user.
- Add a worker startup smoke test that asserts the `realtime_listener_connected` log line appears within 5 seconds of worker boot.
- Periodically grep the backend log for `Tip:` to catch new Lightning chatter slipping through.

## Refs

- `apps/worker/main.py::_realtime_loop`
- `apps/worker/main.py::main` (poll fallback at 30s)
- `packages/forecasting/cache.py::get_or_load_sync` (threading.Lock single-flight)
- `apps/api/main.py` (warning filters + lightning logger)
- BUG-024 (predecessor — dropped asyncio.Lock single-flight)
- BUG-022 (predecessor — 409 swallow on scheduled_cashflows)
- BUG-028 (predecessor — first sklearn warning suppression)
