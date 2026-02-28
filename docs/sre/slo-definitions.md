# SCALE App — SLI/SLO Definitions & Error Budget Policy

## Service Level Indicators (SLIs)

| SLI | Measurement | Data Source |
|-----|------------|-------------|
| **Availability** | Successful HTTP responses (non-5xx) / Total HTTP responses | Sentry performance monitoring |
| **Latency** | % of requests completing in < 500ms | X-Response-Time header / Sentry |
| **Import Success** | Successful CSV imports / Total import attempts | Application logs (structlog) |
| **Classification Accuracy** | User-accepted categories / Total classified | Feedback endpoint tracking |

## Service Level Objectives (SLOs)

| SLO | Target | Error Budget (30 days) | Burn Rate Alert |
|-----|--------|----------------------|-----------------|
| Availability | 99.9% | 43.2 min downtime | >10x = page, >5x = ticket |
| Latency (p95) | 95% under 500ms | 5% of requests may exceed | >20% exceeding = alert |
| Import Success | 99% | 1% of imports may fail | >5% failing = page |
| Classification Accuracy | 85% | 15% may be incorrect | <70% accuracy = retrain model |

## Error Budget Policy

### Budget > 50% remaining
- Ship features normally
- Run chaos experiments
- Accept calculated risk for velocity

### Budget 25-50% remaining
- Slow down feature releases
- Prioritize reliability improvements
- Review recent incidents for patterns

### Budget < 25% remaining
- **FREEZE** feature releases
- All engineering effort on reliability
- Postmortem for budget burn causes
- Architecture review if systemic

### Budget exhausted (0%)
- Only critical bug fixes and security patches
- Mandatory reliability sprint
- Root cause analysis required before resuming features
- Stakeholder communication on recovery plan

## Burn Rate Calculation

```
Burn rate = (error rate observed) / (error rate allowed by SLO)

Example (Availability SLO = 99.9%):
  Allowed error rate = 0.1%
  If observed error rate = 0.5% → burn rate = 5x
  At 5x burn rate, 30-day budget exhausted in 6 days
```

### Alert Thresholds

| Window | Burn Rate | Action | Notification |
|--------|-----------|--------|-------------|
| 5 min | >14x | Page on-call immediately | Sentry critical alert |
| 30 min | >10x | Page on-call | Sentry high alert |
| 6 hours | >5x | Create urgent ticket | Sentry warning |
| 24 hours | >2x | Review in next standup | Sentry info |

## Measurement Cadence

| Activity | Frequency |
|----------|-----------|
| SLO dashboard review | Weekly |
| Error budget status check | Weekly |
| SLO target re-evaluation | Quarterly |
| Full SRE review | Quarterly |
