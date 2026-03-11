# SCALE App — Chaos Engineering Experiments

## Purpose

Validate that the system degrades gracefully under failure conditions. Each experiment tests a specific failure mode and documents the expected vs actual behavior.

Run experiments in staging only. Never in production without error budget > 50%.

---

## Experiment 1: Kill API Container

**Hypothesis:** Docker restart policy recovers the API within 30 seconds. No requests are lost during recovery (clients retry).

| Field | Value |
|-------|-------|
| Target | API container |
| Method | `docker kill scale-api` |
| Duration | Until auto-restart completes |
| Blast radius | All API traffic |
| Rollback | Automatic (restart policy: unless-stopped) |

**Steps:**

1. Verify API healthy: `curl /api/v1/health`
2. Kill container: `docker kill $(docker compose ps -q api)`
3. Monitor: `watch -n 1 'curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health'`
4. Measure time to recovery

**Expected:** New container healthy within 30s. Health check passes. No data corruption.

**Result:** _Run and fill in_

---

## Experiment 2: Redis Unreachable

**Hypothesis:** API continues serving requests without Redis. Rate limiting disabled (fail-open). Celery queue paused. Health readiness reports degraded.

| Field | Value |
|-------|-------|
| Target | Redis connection |
| Method | `docker compose stop redis` |
| Duration | 5 minutes |
| Blast radius | Rate limiting, caching, Celery queue |
| Rollback | `docker compose start redis` |

**Steps:**

1. Verify all healthy: `curl /api/v1/health/ready`
2. Stop Redis: `docker compose stop redis`
3. Test API still serves: `curl /api/v1/health` (should return 200)
4. Test readiness: `curl /api/v1/health/ready` (should return 503, redis=down)
5. Test rate limiter: rapid requests should all pass (fail-open)
6. Restart Redis: `docker compose start redis`
7. Verify full recovery

**Expected:** API serves traffic. Rate limiting disabled. Readiness shows degraded. Full recovery after Redis restart.

**Result:** _Run and fill in_

---

## Experiment 3: Slow Database Queries

**Hypothesis:** Slow queries return 408/504 timeout rather than hanging indefinitely. No connection pool exhaustion.

| Field | Value |
|-------|-------|
| Target | Supabase Postgres |
| Method | `SET statement_timeout = '100ms'` on test connection |
| Duration | 10 minutes |
| Blast radius | Queries exceeding 100ms |
| Rollback | `RESET statement_timeout` |

**Steps:**

1. Connect to Supabase SQL editor
2. Set timeout: `ALTER DATABASE postgres SET statement_timeout = '100ms';`
3. Run k6 load test targeting transaction listing
4. Monitor for hung connections and error responses
5. Reset: `ALTER DATABASE postgres RESET statement_timeout;`

**Expected:** Slow queries fail fast with timeout error. API returns 500 with RFC 7807 detail. Connection pool not exhausted.

**Result:** _Run and fill in_

---

## Experiment 4: High Concurrent Imports

**Hypothesis:** Queue handles burst of imports without data loss. Rate limiting kicks in for excessive requests. Import deduplication prevents duplicate transactions.

| Field | Value |
|-------|-------|
| Target | Ingestion endpoint |
| Method | k6 with 50 concurrent CSV uploads |
| Duration | 2 minutes |
| Blast radius | Import pipeline |
| Rollback | N/A (idempotent via fingerprint dedup) |

**Steps:**

1. Prepare test CSV file with known transaction count
2. Run: `k6 run --vus 50 --duration 2m import_stress_test.js`
3. Verify: count transactions in DB matches expected (no duplicates, no losses)
4. Check rate limiter: some requests should get 429

**Expected:** All valid transactions imported exactly once. Rate limiter returns 429 for excess. No data loss or corruption.

**Result:** _Run and fill in_

---

## Experiment 5: Worker Crash Mid-Training

**Hypothesis:** Training job status transitions to "failed". User can retry. No orphaned resources.

| Field | Value |
|-------|-------|
| Target | Celery worker during training |
| Method | `kill -9 <worker_pid>` during active training job |
| Duration | Until job status resolves |
| Blast radius | Single training job |
| Rollback | Restart worker, job auto-retries or marked failed |

**Steps:**

1. Start a training job via API
2. Verify status = "processing"
3. Kill worker: `docker compose kill worker`
4. Wait 5 minutes
5. Check job status: should be "failed" (via cleanup task) or "processing" (if retry pending)
6. Restart worker: `docker compose up -d worker`
7. Verify cleanup task marks stale job as failed within 1 hour

**Expected:** Job eventually marked "failed". Checkpoint files not corrupted. User can retry. Cleanup automation handles orphaned jobs.

**Result:** _Run and fill in_

---

## Schedule

| Experiment | Frequency | Prerequisites |
|-----------|-----------|---------------|
| Kill API container | Monthly | Staging environment |
| Redis unreachable | Monthly | Staging environment |
| Slow DB queries | Quarterly | Staging Supabase |
| High concurrent imports | Quarterly | Test data + staging |
| Worker crash | Quarterly | Active training job |
