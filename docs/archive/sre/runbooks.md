# SCALE App — Operational Runbooks

## Runbook: API Returns 503

**Severity:** SEV1 (if sustained > 5 min)
**SLO Impact:** Availability

### Detection

- Sentry alert: health check fails 3x consecutive
- Docker healthcheck fails → container restart loop
- User reports: "Service unavailable"

### Triage (< 5 min)

```bash
# 1. Check health endpoint directly
curl -s http://localhost:8000/api/v1/health | jq .
curl -s http://localhost:8000/api/v1/health/ready | jq .

# 2. Check container status
docker compose ps

# 3. Check recent logs
docker compose logs api --tail=50
```

### Mitigation

1. **If Redis down:** Check Upstash dashboard. Redis auto-recovers. API degrades gracefully (rate limiting disabled, fail-open).
2. **If DB unreachable:** Check Supabase dashboard → Status page. Verify connection pool isn't exhausted.
3. **If container crash loop:** Check logs for OOM or unhandled exception. Restart: `docker compose restart api`
4. **If model not loaded:** Cold start takes 15-30s. Wait for healthcheck to pass.

### Resolution

- Fix root cause (deploy fix, scale resources, restore dependency)
- Verify: `curl /api/v1/health/ready` returns 200

### Escalation

- If not resolved in 15 min → escalate to team lead
- If Supabase outage → check status.supabase.com, nothing to do but wait

---

## Runbook: Training Job Stuck in "processing"

**Severity:** SEV3 (single user affected)
**SLO Impact:** Import Success

### Detection

- Sentry alert: job status = "processing" for > 1 hour
- User reports: training never completes
- Cleanup task marks job as failed automatically

### Triage

```bash
# 1. Check worker logs
docker compose logs worker --tail=50

# 2. Check Redis queue depth
docker compose exec redis redis-cli LLEN training

# 3. Check job status in DB
# Via Supabase dashboard or SQL:
# SELECT * FROM training_jobs WHERE status = 'processing' AND created_at < NOW() - INTERVAL '1 hour';
```

### Mitigation

1. **If worker crashed:** Restart worker. Job will auto-retry (Celery acks_late).

   ```bash
   docker compose restart worker
   ```

2. **If stuck > 1 hour:** Mark as failed via service-role:

   ```sql
   UPDATE training_jobs SET status = 'failed', error_message = 'Timed out after 1 hour'
   WHERE id = '<job_id>' AND status = 'processing';
   ```

3. Notify user to retry.

### Prevention

- `cleanup_stale_training_jobs` Celery beat task runs hourly to auto-fail stuck jobs
- Celery `task_time_limit=3600` kills tasks exceeding 1 hour

---

## Runbook: Redis Down / Unreachable

**Severity:** SEV2 (degraded, not down)
**SLO Impact:** Latency (no caching), Availability (if rate limiter misconfigured)

### Detection

- Health readiness endpoint returns `"redis": "down"` or `"redis": "timeout"`
- Sentry warning: `redis_health_failed`
- Rate limiting stops working (fail-open behavior)

### Triage

```bash
# 1. Check Redis container
docker compose ps redis
docker compose logs redis --tail=20

# 2. Test connectivity
docker compose exec redis redis-cli ping

# 3. Check memory usage
docker compose exec redis redis-cli info memory | grep used_memory_human
```

### Mitigation

1. **If local Redis crashed:** Restart: `docker compose restart redis`
2. **If Upstash (production):** Check Upstash dashboard. Usually auto-recovers.
3. **API continues working** — rate limiting and caching disabled (fail-open), Celery queue paused.

### Resolution

- Verify Redis back: `redis-cli ping` → PONG
- Verify API readiness: `curl /api/v1/health/ready` shows `"redis": "up"`
- Check Celery worker reconnected: `docker compose logs worker --tail=10`

---

## Runbook: High Error Rate (> 5% 5xx)

**Severity:** SEV1
**SLO Impact:** Availability

### Detection

- Sentry alert: error rate > 5% sustained for 5 min
- Spike in 5xx responses in structured logs

### Triage

```bash
# 1. Check Sentry for error grouping — is it one endpoint or many?
# 2. Check recent deployments
git log --oneline -5

# 3. Check application logs for patterns
docker compose logs api --tail=100 | grep '"level": "error"'
```

### Mitigation

1. **If caused by recent deploy:** Roll back immediately.

   ```bash
   # Revert to previous commit
   git revert HEAD
   # Redeploy
   ```

2. **If dependency failure (DB, Redis, external API):** Follow the relevant runbook above.
3. **If traffic spike:** Scale workers if applicable. Rate limiting should auto-throttle.

---

## Runbook: Slow Responses (p95 > 2s)

**Severity:** SEV2
**SLO Impact:** Latency

### Detection

- Sentry performance alert: p95 > 2s for 10 min
- X-Response-Time headers showing high values
- User reports: "app is slow"

### Triage

```bash
# 1. Identify slow endpoints from logs
# Look for high duration_ms in structured logs

# 2. Check DB query performance
# Supabase dashboard → SQL Editor:
# SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 5;

# 3. Check Redis latency
docker compose exec redis redis-cli --latency
```

### Mitigation

1. **If specific endpoint:** Check for N+1 queries, missing indexes, large payloads
2. **If DB-wide:** Check connection pool saturation, run ANALYZE on affected tables
3. **If HypCD model:** Cold start takes 15-30s. Once loaded, classify should be < 200ms.
4. **If memory pressure:** Check container resource limits, consider scaling

---

## Incident Severity Levels

| Level | Definition | Response Time | Examples |
|-------|-----------|---------------|----------|
| SEV1 | Full service outage | < 15 min | API 503, DB down, all requests failing |
| SEV2 | Degraded service | < 1 hour | Redis down, slow responses, partial failures |
| SEV3 | Minor issue | < 4 hours | Single user affected, non-critical feature broken |
