# Incident Runbook: Redis Down / Unreachable

## 1. Overview

**What happened:** The SCALE Application has lost connectivity to the Redis cluster.
**Primary Impact:** Background tasks (Celery) are paused, and rate limiting degrades to fail-open mode.
**Urgency:** MEDIUM to HIGH. Fast degradation if traffic spikes while rate limiting is disabled.

## 2. Initial Triaging

1. **Validate the Alert:**
   - Check the `RedisAvailability` metric or check the connection directly from the API.
   - Look at API logs in Sentry/structlog for `redis.exceptions.ConnectionError`.

2. **Check Rate Limiter State:**
   - Due to the fail-open design in `rate_limiter.py`, the API should still be serving normal traffic. Verify `200 OK` responses are processing on core endpoints.

## 3. Investigation Steps

### A. Managed Service Provider (Upstash / AWS ElastiCache)

- Check the provider dashboard. Is there an ongoing maintenance window or an outage?
- Has the connection string or password changed recently?

### B. Network Connectivity

- From an API container, try to ping or telnet the Redis port: `telnet <REDIS_HOST> 6379`.
- Verify VPC/Security Group rules haven't been modified restricting port 6379.

### C. Resource Exhaustion

- Check Redis memory usage. Did we hit the `maxmemory` limit?
- **Action:** If memory is full, configure `volatile-lru` eviction policy or flush non-essential keys if cache is expendable.

## 4. Remediation & Recovery

- **If Provider is Down:** Wait for the provider SLA to kick in or spin up a fallback containerized Redis temporarily and update `.env`.
- **If Memory is Exhausted:** Increase instance size or clear Celery results queue.
- **Restore Worker Queue:** Once Redis is back, monitor Celery workers (`WorkerQueueBackedUp` alert) to ensure they reconnect and process the backlog. Restart worker pods if they are stuck attempting prior connections.

## 5. Post-Incident Requirements

- Ensure no excessive traffic slipped past the disabled rate limiter during the fail-open period.
- Measure the time Redis was down and tune retry logic if the workers didn't reconnect automatically.
