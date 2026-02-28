# SCALE API — SLO & Error Budget Policy

## 1. Overview

This document defines the Service Level Objectives (SLOs), Service Level Indicators (SLIs), and Error Budget policies for the SCALE API. The goal is to balance reliability with feature velocity by relying on quantitative metrics rather than intuition.

## 2. Core SLIs & SLOs

| Service Focus         | SLI (Service Level Indicator)                                                                               | SLO Target             | Error Budget (Monthly)       |
| :-------------------- | :---------------------------------------------------------------------------------------------------------- | :--------------------- | :--------------------------- |
| **Availability**      | The proportion of successful HTTP requests (`2xx`, `3xx`, `4xx` excluding `429`) over total valid requests. | **99.9%**              | ~43.2 minutes of downtime    |
| **Latency (p95)**     | The 95th percentile of response times for all synchronous API endpoints.                                    | **< 2000ms (95%)**     | 5% of requests may exceed 2s |
| **Worker Processing** | Time taken from training job enqueue to status switching to `processing`.                                   | **< 15 minutes (99%)** | 1% of jobs may wait > 15m    |

> **Note on HTTP `429` / `400` status codes:**
> Client errors (like invalid input or legitimate rate-limiting) do _not_ count against the availability error budget. Only unexpected server errors (`5xx`) burn the budget.

## 3. Error Budget Policy

The error budget is the allowed amount of failure per 30-day sliding window.

### 3.1 Normal Operation (Budget > 0%)

- **Action:** Feature development proceeds normally.
- **On-Call:** Responds to fast-burn alerts (Critical) and investigates slow-burn alerts (Warning).

### 3.2 Moderate Exhaustion (Budget < 25%)

- **Action:** Engineering manager is notified. Team assesses remaining features for the sprint and prioritizes stabilizing work (reducing toil, addressing technical debt) if the trend is accelerating.

### 3.3 Complete Exhaustion (Budget = 0%)

If the 30-day error budget is fully consumed:

- **Action:** **Feature Freeze.** All new feature deployments to production are halted.
- **Focus:** 100% of engineering effort shifts to reliability fixes, performance improvements, and resolving the root causes of the budget burn.
- **Exceptions:** Security patches (CVEs) and critical bug fixes that restore reliability are permitted.
- **Resume:** Normal feature deployment resumes once the 30-day sliding window regains at least 5% of the error budget.

## 4. Alerting Strategy (Burn Rates)

We alert based on the _rate_ at which the error budget is being consumed, rather than simple thresholds.

- **Critical (Page On-Call):** Fast Burn. Budget will be exhausted in < 2 days. Requires immediate intervention (e.g., `ApiDown`, `HighErrorRate` > 5%).
- **Warning (Ticket/Slack):** Slow Burn. Budget will be exhausted in < 7 days. Requires investigation during business hours (e.g., `HighLatency`, `WorkerQueueBackedUp`).

_Last updated: March 2026_
