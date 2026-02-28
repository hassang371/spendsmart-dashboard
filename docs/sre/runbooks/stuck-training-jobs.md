# Incident Runbook: Stuck Training Jobs

## 1. Overview

**What happened:** One or more ML training jobs are stuck in the `processing` state in the database and have not completed or failed within the expected timeout (e.g., 2 hours).
**Primary Impact:** Users cannot launch new training jobs (concurrency limits). Infrastructure resources may be wasting money on zombie tasks.
**Urgency:** LOW to MEDIUM (Warning Status). Needs resolution within business hours.

## 2. Initial Triaging

1. **Identify the Stuck Job(s):**
   - Query the DB: `SELECT id, status, updated_at FROM classification_jobs WHERE status = 'processing' AND updated_at < NOW() - INTERVAL '2 hours';`
2. **Determine Worker Status:**
   - Is the Celery worker pod still alive and crunching numbers? Check CPU usage of the `scale-worker` container.
   - If CPU is 0%, the job is a dead "zombie" that failed to update the database upon crash.

## 3. Investigation Steps

### A. Did the Worker Crash? (OOMKilled)

- ML training is memory-intensive. Check Kubernetes/Docker events for `OOMKilled`.
- **Root Cause Fix:** The batch size was too large or the container memory limit is too low.

### B. Is the Celery Task Hanging?

- Did the task hang during an external API call (e.g., downloading large datasets from Supabase)?
- Verify HTTP timeouts are strictly configured in the service layer.

## 4. Remediation & Recovery

1. **Manual State Correction:**
   - Force update the stuck jobs to `failed` so users can try again.
   - `UPDATE classification_jobs SET status = 'failed', error_message = 'Job timed out manually' WHERE status = 'processing' AND updated_at < NOW() - INTERVAL '2 hours';`
2. **Kill Zombie Workers:**
   - If a pod is legitimately hung, restart the Celery worker deployment: `kubectl rollout restart deployment scale-worker`.

## 5. Post-Incident Requirements

- **Toil Reduction:** Ensure the automated Celery Beat task (`cleanup_stale_jobs`) is configured properly to handle this scenario without human intervention next time.
- **Memory Tuning:** Adjust `batch_size` in the `trainer.py` if OOM was the culprit.
