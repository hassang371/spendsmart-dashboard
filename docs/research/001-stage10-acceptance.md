# Stage 10 — Integration + Verification Acceptance Record

> **Date:** 2026-05-05
> **Scope:** Master plan `docs/plans/2026-04-17-prediction-engine-v1-master.md` §Stage 10
> **Branch:** `feature/prediction-engine-v1`

## DB-backed test runs

13 of 14 DB-flagged tests pass against the live local Supabase stack. The 14th (`test_atomic_claim_skips_locked`) remains an explicit skip — documented in the test itself: `FOR UPDATE SKIP LOCKED` requires two racing Postgres sessions, and `supabase-py` serialises requests on a single connection. Manual `psql` coverage is the agreed mitigation.

```
apps/api/core/tasks/tests/test_evaluate_predictions.py            7 passed, 1 skipped
apps/api/domains/forecasting/tests/test_intents_cascade.py         1 passed
apps/api/domains/forecasting/tests/test_log_user_prediction_rpc_hardening.py   3 passed
apps/api/domains/forecasting/tests/test_user_predictions_rpc.py    2 passed
                                                                 13 passed, 1 skipped
```

`stack_available()` runtime gate is the chosen pattern. Tests auto-run when the local stack answers, auto-skip otherwise — devs never see hard failures from a missing `supabase start`.

Full unit-test suite still green: **515 passed, 1 skipped** across `packages/forecasting`, `apps/worker`, `apps/api`.

## Curl smoke against `/forecast` endpoints

Backend serving on `localhost:8000`. Probes from a logged-out client:

| Endpoint | Status | Latency | Gate |
|---|---|---|---|
| `GET /health` | 200 | 0.5ms | open |
| `GET /api/v1/forecast/predict?horizon=30` | 401 | 1.3ms | `get_current_user_id` |
| `GET /api/v1/forecast/intents` | 401 | <2ms | `get_current_user_id` |
| `GET /api/v1/forecast/safe-to-spend` | 401 | <2ms | `get_current_user_id` |

Auth gate is functioning: every protected endpoint short-circuits before any DB or model work.

## Browser smoke — `/dashboard/insights`

Validated end-to-end during the Stage 10 ride-out (Hassan's screenshots, 2026-05-04 evening session):

| Capability | State |
|---|---|
| Cold-start flow (no checkpoint → chronos2 forecast served) | ✅ |
| Auto-enqueue training_jobs INSERT on first cold predict | ✅ (logs: `training_auto_enqueued days=157`) |
| Worker push pickup via Realtime (BUG-031) | ✅ (`realtime_listener_connected` within 5s of boot) |
| Full-history pagination (3083 of 3083 transactions, 4 pages × 1000) | ✅ (BUG-028) |
| TFT training succeeds on M-series CPU, ~5 min, val_loss = 5118.875 | ✅ |
| Cache invalidation on completion via Redis pub-sub | ✅ (`cache_invalidated_via_pubsub`) |
| Browser auto-refresh on completion via Realtime UPDATE | ✅ (BUG-030 REPLICA IDENTITY FULL migration applied) |
| Ensemble path engaged (`model_type = tft(0.7)+chronos(0.3)`) | ✅ |
| Fan chart renders all three bands (P2–P98, P10–P90, P25–P75) | ✅ (BUG-029 monotonic enforcement) |
| Variable importance populated | ✅ (BUG-030 dict unwrap) |
| Forecast anchored to user's current balance | ✅ (BUG-032) |
| Cold-start banner reflects in-flight training state | ✅ (BUG-032) |

## Verdict

Stage 10 acceptance criteria satisfied. The single deferred concurrency test is documented, not blocking. Live ride-out through Hassan's browser confirmed every capability the master plan called for.
