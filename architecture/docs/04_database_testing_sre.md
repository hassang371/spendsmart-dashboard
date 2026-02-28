# SCALE App — Database Optimization, Testing Strategy & SRE Practices

---

## 1. Database Optimization

### 1.1 Current Schema Audit

**Tables:** 2 (`transactions`, `training_jobs`) + 1 missing (`uploaded_files`)  
**Indexes:** 5 total  
**RLS:** Enabled on both tables  
**Extensions:** `uuid-ossp`

#### Current Index Assessment

| Index                                                                   | Used By            | Status                                         |
| ----------------------------------------------------------------------- | ------------------ | ---------------------------------------------- |
| `idx_transactions_user_date` (user_id, transaction_date)                | Dashboard queries  | ✅ Good                                        |
| `idx_transactions_category` (category)                                  | Category filtering | ⚠️ Low selectivity — categories are few values |
| `idx_transactions_user_fingerprint` (user_id, fingerprint) UNIQUE       | Dedup on import    | ✅ Critical                                    |
| `idx_training_jobs_pending` (status, created_at) WHERE status='pending' | Worker polling     | ✅ Excellent — partial index                   |
| `idx_training_jobs_user_status` (user_id, status, created_at DESC)      | User's latest job  | ✅ Good                                        |

#### Missing Indexes

| Needed For                     | Proposed Index                                                    | Rationale                               |
| ------------------------------ | ----------------------------------------------------------------- | --------------------------------------- |
| Transaction search by merchant | `idx_transactions_user_merchant (user_id, merchant_name)`         | Merchant-based filtering on dashboard   |
| JSONB raw_data queries         | `idx_transactions_raw_data USING GIN(raw_data)`                   | Query structured fields inside raw_data |
| Keyset pagination              | `idx_transactions_pagination (user_id, created_at DESC, id DESC)` | Cursor-based pagination (no OFFSET)     |
| Amount range filtering         | `idx_transactions_user_amount (user_id, amount)`                  | Budget analysis, amount filtering       |

### 1.2 Diagnostic Queries

Run these on Supabase SQL Editor to understand current performance:

```sql
-- 1. Enable pg_stat_statements (run once)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 2. Top slow queries
SELECT
    round(total_exec_time::numeric, 2) as total_time_ms,
    calls,
    round(mean_exec_time::numeric, 2) as mean_time_ms,
    query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;

-- 3. Tables with sequential scans (should be 0 for large tables)
SELECT schemaname, tablename, seq_scan, idx_scan,
       round(100.0 * idx_scan / NULLIF(seq_scan + idx_scan, 0), 2) as idx_scan_pct
FROM pg_stat_user_tables
ORDER BY seq_scan DESC;

-- 4. Cache hit ratio (target: > 99%)
SELECT
    sum(heap_blks_hit) as cache_hits,
    sum(heap_blks_read) as disk_reads,
    round(100.0 * sum(heap_blks_hit) / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0), 2) as cache_hit_ratio
FROM pg_statio_user_tables;

-- 5. Table sizes
SELECT
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
    n_live_tup as live_rows,
    n_dead_tup as dead_rows
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- 6. Unused indexes (safe to drop after 30 days)
SELECT indexname, idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes
WHERE idx_scan = 0 AND indexrelname NOT LIKE 'pg_toast%'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### 1.3 Query Patterns & Optimization

#### Dashboard — User's Recent Transactions

```sql
-- Current: likely using OFFSET pagination
SELECT * FROM transactions
WHERE user_id = $1
ORDER BY transaction_date DESC
LIMIT 50 OFFSET 200;
-- Problem: OFFSET 200 scans 250 rows

-- Optimized: Keyset pagination (cursor-based)
SELECT * FROM transactions
WHERE user_id = $1
  AND (transaction_date, id) < ($2, $3)  -- cursor from previous page
ORDER BY transaction_date DESC, id DESC
LIMIT 50;
-- Index: idx_transactions_pagination (user_id, transaction_date DESC, id DESC)
```

#### Import — Batch Upsert with Dedup

```sql
-- Current: individual INSERT with ON CONFLICT per row
-- Problem: N round-trips for N rows

-- Optimized: Batch upsert (1 round-trip for 1000 rows)
INSERT INTO transactions (user_id, transaction_date, amount, description,
                          merchant_name, category, payment_method, fingerprint, raw_data)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9),
       ($10, $11, ...),
       ...  -- Up to 1000 rows per batch
ON CONFLICT (user_id, fingerprint)
DO NOTHING
RETURNING id;
-- Already optimized via existing UNIQUE index
```

#### Category Stats — Dashboard Aggregation

```sql
-- Slow: COUNT + GROUP BY on every page load
SELECT category, COUNT(*), SUM(amount)
FROM transactions
WHERE user_id = $1
GROUP BY category;

-- Phase 2: Materialized view (refresh every 5 min)
CREATE MATERIALIZED VIEW user_category_stats AS
SELECT user_id, category, COUNT(*) as count, SUM(amount) as total
FROM transactions
GROUP BY user_id, category;

CREATE UNIQUE INDEX idx_user_category_stats
ON user_category_stats (user_id, category);

-- Refresh in background
REFRESH MATERIALIZED VIEW CONCURRENTLY user_category_stats;
```

### 1.4 Connection Pooling Strategy

| Phase   | Method                        | Config                                                          |
| ------- | ----------------------------- | --------------------------------------------------------------- |
| Phase 1 | Supabase built-in PgBouncer   | Transaction mode, 20 connections (free tier)                    |
| Phase 2 | Supabase Pro PgBouncer        | Transaction mode (API), Session mode (workers), 200 connections |
| Phase 3 | Self-managed PgBouncer on K8s | Transaction mode, 1000+ connections, connection queueing        |

**FastAPI connection management:**

```python
# Use async Supabase client with connection pooling
# Reuse client per-request via dependency injection
async def get_supabase(request: Request) -> AsyncClient:
    return request.app.state.supabase  # Singleton, shared across requests
```

### 1.5 Future: Table Partitioning (Phase 3, 1M+ users)

```sql
-- Partition transactions by month for fast range queries
CREATE TABLE transactions_partitioned (
    LIKE transactions INCLUDING ALL
) PARTITION BY RANGE (transaction_date);

-- Auto-create monthly partitions
CREATE TABLE transactions_2026_01 PARTITION OF transactions_partitioned
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
-- ... (automate with pg_partman extension)
```

### 1.6 VACUUM & Maintenance

Supabase handles autovacuum automatically. For high-churn tables (once transactions table grows):

```sql
-- Set aggressive autovacuum for transactions table
ALTER TABLE transactions SET (
    autovacuum_vacuum_scale_factor = 0.05,     -- Vacuum at 5% dead tuples (default 20%)
    autovacuum_analyze_scale_factor = 0.02,    -- Analyze at 2% changes
    autovacuum_vacuum_cost_delay = 2           -- Faster vacuum
);
```

---

## 2. Testing Strategy

### 2.1 Test Pyramid

```
         ╱╲
        ╱  ╲        E2E Tests (10%)
       ╱ E2E╲       • Full import flow via browser
      ╱──────╲      • Login → import → classify → view
     ╱        ╲
    ╱Integration╲   Integration Tests (20%)
   ╱   Tests    ╲   • API endpoint tests (FastAPI TestClient)
  ╱──────────────╲  • DB roundtrip tests
 ╱                ╲
╱   Unit Tests     ╲ Unit Tests (70%)
╱───────────────────╲• Pure function tests (fingerprint, schemas)
                      • Service layer tests (mocked DB)
```

### 2.2 Test Specs Per Domain

#### Ingestion Domain

| Test Name                             | Type        | What It Tests                    |
| ------------------------------------- | ----------- | -------------------------------- |
| `test_fingerprint_deterministic`      | Unit        | Same input → same fingerprint    |
| `test_fingerprint_canonical_fields`   | Unit        | Uses all 6 canonical fields      |
| `test_fingerprint_ignores_whitespace` | Unit        | Normalizes whitespace/case       |
| `test_import_valid_csv`               | Integration | CSV upload → correct DB inserts  |
| `test_import_dedup_skips`             | Integration | Duplicate fingerprints → skipped |
| `test_import_zero_amount_skipped`     | Integration | Zero amounts → filtered out      |
| `test_import_pydantic_validation`     | Unit        | Invalid input → 422 with details |

#### Categorization Domain

| Test Name                           | Type        | What It Tests                                |
| ----------------------------------- | ----------- | -------------------------------------------- |
| `test_classifier_singleton`         | Unit        | HypCD initialized once on startup            |
| `test_classify_single`              | Integration | POST /classify → valid category              |
| `test_classify_batch_no_n_plus_1`   | Integration | 100 items → 1 batch call, not 100 individual |
| `test_classify_feedback_updates_db` | Integration | User correction → stored for retraining      |

#### Core Infrastructure

| Test Name                              | Type        | What It Tests                          |
| -------------------------------------- | ----------- | -------------------------------------- |
| `test_error_handler_rfc7807`           | Unit        | All errors → RFC 7807 format           |
| `test_error_includes_request_id`       | Unit        | Error responses contain X-Request-ID   |
| `test_auth_valid_jwt`                  | Unit        | Valid Supabase JWT → user_id extracted |
| `test_auth_expired_jwt`                | Unit        | Expired token → 401                    |
| `test_auth_missing_jwt`                | Unit        | No Authorization header → 401          |
| `test_rate_limiter_allows_under_limit` | Integration | 5 requests → all pass                  |
| `test_rate_limiter_blocks_over_limit`  | Integration | 101 requests → 429                     |
| `test_cors_allows_configured_origin`   | Integration | Correct origin → allowed               |
| `test_cors_blocks_unknown_origin`      | Integration | Random origin → blocked                |
| `test_health_liveness`                 | Integration | GET /health → 200                      |
| `test_health_readiness_all_up`         | Integration | All deps up → 200                      |
| `test_health_readiness_redis_down`     | Integration | Redis down → 503                       |

### 2.3 Coverage Targets

| Domain            | Target  | Rationale                              |
| ----------------- | ------- | -------------------------------------- |
| `ingestion/`      | 95%     | Financial data — must be correct       |
| `core/auth.py`    | 95%     | Security critical                      |
| `core/errors.py`  | 90%     | Error handling                         |
| `categorization/` | 85%     | ML integration has unpredictable paths |
| `forecasting/`    | 80%     | Heavy ML code                          |
| `training/`       | 80%     | Worker tasks                           |
| `accounts/`       | 85%     | User data                              |
| **Overall**       | **80%** | Industry standard for fintech          |

### 2.4 Performance Testing (Phase 2)

```javascript
// k6 load test: apps/api/tests/performance/load_test.js
import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 20 }, // Ramp up to 20 users
    { duration: "1m", target: 20 }, // Sustain
    { duration: "10s", target: 0 }, // Ramp down
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"], // 95% under 500ms
    http_req_failed: ["rate<0.01"], // <1% errors
  },
};

export default function () {
  const headers = { Authorization: `Bearer ${__ENV.TEST_JWT}` };

  // Health check
  check(http.get(`${__ENV.API_URL}/api/v1/health`), {
    "health 200": (r) => r.status === 200,
  });

  // Transaction listing
  check(
    http.get(`${__ENV.API_URL}/api/v1/accounts/transactions`, { headers }),
    {
      "transactions 200": (r) => r.status === 200,
      "transactions < 500ms": (r) => r.timings.duration < 500,
    },
  );

  sleep(1);
}
```

### 2.5 Security Testing Checklist

| Test                       | Tool                  | When                 |
| -------------------------- | --------------------- | -------------------- |
| SQL injection              | Bandit (Python SAST)  | Every PR (CI)        |
| Dependency vulnerabilities | pip-audit + npm audit | Every PR (CI)        |
| Secret exposure            | Gitleaks              | Every commit (CI)    |
| Container vulnerabilities  | Trivy                 | On Docker build (CI) |
| Auth bypass                | Manual test suite     | Before each release  |
| Rate limit bypass          | k6 script             | Quarterly            |
| CORS misconfiguration      | Integration test      | Every PR             |

---

## 3. SRE Practices

### 3.1 SLI/SLO Definitions

| SLO                         | SLI (Measurement)                                | Target | Error Budget (30 days) | Burn Rate Alert           |
| --------------------------- | ------------------------------------------------ | ------ | ---------------------- | ------------------------- |
| **Availability**            | Successful HTTP responses / Total HTTP responses | 99.9%  | 43.2 min downtime      | >10x = page, >5x = ticket |
| **Latency**                 | % of requests completing in < 500ms              | 95%    | 5% may exceed          | >20% exceeding = alert    |
| **Import Success**          | Successful imports / Total imports               | 99%    | 1% may fail            | >5% failing = page        |
| **Classification Accuracy** | User-accepted categories / Total classified      | 85%    | 15% may be wrong       | <70% = retrain model      |

### 3.2 Error Budget Policy

```
If error budget remaining > 50%:
  → Ship features normally
  → Run chaos experiments
  → Accept risk for speed

If error budget remaining 25-50%:
  → Slow down feature releases
  → Focus on reliability improvements
  → Review recent incidents

If error budget remaining < 25%:
  → FREEZE feature releases
  → All engineering effort on reliability
  → Postmortem for budget burn causes

If error budget exhausted:
  → Only critical bug fixes
  → Mandatory reliability sprint
  → Architecture review
```

### 3.3 Incident Management Process

```
1. DETECT (< 5 min)
   └─ Sentry alert / health check failure / user report
       ↓
2. TRIAGE (< 10 min)
   └─ Severity: SEV1 (full outage) / SEV2 (degraded) / SEV3 (minor)
       ↓
3. MITIGATE (< 30 min for SEV1)
   └─ Rollback / feature flag / scale up / restart
       ↓
4. RESOLVE (< 4 hours for SEV1)
   └─ Root cause fix → test → deploy
       ↓
5. POSTMORTEM (within 48 hours)
   └─ Blameless analysis → action items → share learnings
```

### 3.4 Toil Reduction Targets

| Current Toil                   | Automation                          | Phase           |
| ------------------------------ | ----------------------------------- | --------------- |
| Manual database schema updates | Supabase CLI migrations             | M4              |
| Manual deploy process          | GitHub Actions CD pipeline          | M4              |
| Manual health monitoring       | Sentry alerts + health endpoints    | M5              |
| Manual log review              | Structured logging + Sentry search  | M5              |
| Manual training job monitoring | SSE streaming + auto-status updates | M1 (BUG-01 fix) |

### 3.5 Chaos Engineering (Phase 2+)

| Experiment                | What It Tests             | How                               | Expected Result                                     |
| ------------------------- | ------------------------- | --------------------------------- | --------------------------------------------------- |
| Kill API container        | Auto-restart and recovery | `docker kill scale-api`           | New container within 30s                            |
| Redis unreachable         | Graceful degradation      | Block Redis port                  | API works (no rate limits, no cache), logs warnings |
| Slow DB queries           | Timeout handling          | `SET statement_timeout = '100ms'` | 408 returned, no hung connections                   |
| High concurrent imports   | Queue backpressure        | k6 with 50 concurrent imports     | Queue handles, no data loss                         |
| Worker crash mid-training | Job status consistency    | `kill -9` worker during training  | Job status → "failed", user can retry               |

### 3.6 Runbook: Common Failure Scenarios

#### API Returns 503

```
1. Check: curl /api/v1/health/ready
2. If Redis down: Check Upstash dashboard, wait for auto-recovery
3. If DB down: Check Supabase dashboard, check connection pool
4. If model not loaded: Restart API container
5. Escalate if not resolved in 15 min
```

#### Training Job Stuck in "processing"

```
1. Check Celery worker logs: docker compose logs worker
2. Check Redis queue: redis-cli LLEN training
3. If worker crashed: Restart, job will auto-retry
4. If stuck > 1 hour: Mark as failed via service-role:
   UPDATE training_jobs SET status = 'failed' WHERE id = $job_id;
5. Notify user to retry
```

---

## Skills Usage Summary

| Skill                  | Used For                                             | Key Outputs                                        |
| ---------------------- | ---------------------------------------------------- | -------------------------------------------------- |
| architecture-designer  | System design, domain modules, architecture patterns | System design doc, data flow diagrams              |
| api-designer           | REST design, OpenAPI, pagination, versioning         | API protocol stack, endpoint catalog               |
| devops-engineer        | Docker, docker-compose, CI/CD, migrations            | Dockerfile, workflows, deployment strategy         |
| monitoring-expert      | Logging, alerting, Four Golden Signals               | Structured logging, health checks, alerting        |
| secure-code-guardian   | OWASP, security headers, rate limiting               | Middleware stack, CORS, rate limiter               |
| **database-optimizer** | Index strategy, query optimization, partitioning     | Index audit, diagnostic queries, keyset pagination |
| **sre-engineer**       | SLOs, error budgets, incident management             | SLO definitions, runbooks, chaos experiments       |
| **test-master**        | Test strategy, coverage, automation                  | Test pyramid, per-domain specs, k6 scripts         |
