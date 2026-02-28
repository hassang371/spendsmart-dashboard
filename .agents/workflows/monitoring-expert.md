---
description: Monitoring and observability strategy, implementation, and troubleshooting. Use for designing metrics/logs/traces systems, setting up Prometheus/Grafana/Loki, creating alerts and dashboards, calculating SLOs and error budgets, analyzing performance issues, and comparing monitoring tools (Datadog, ELK, CloudWatch). Covers the Four Golden Signals, RED/USE methods, OpenTelemetry instrumentation, log aggregation patterns, and distributed tracing.
---

# Monitoring & Observability

## When to Use

Use for ANY monitoring, alerting, or observability work:

- Designing metrics systems (Four Golden Signals, RED/USE methods)
- Setting up Prometheus, Grafana, Loki, or Datadog
- Creating alerts and dashboards
- Calculating SLOs and error budgets
- Implementing OpenTelemetry distributed tracing
- Comparing monitoring tools

## Process

1. **Read** `.agents/skills/monitoring-expert/SKILL.md` for the full framework
2. Use bundled automation scripts in `scripts/`:
   - `analyze_metrics.py` — Analyze existing metrics for gaps
   - `alert_quality_checker.py` — Audit alert rules quality
   - `slo_calculator.py` — Calculate SLOs and error budgets
   - `log_analyzer.py` — Analyze log patterns
   - `dashboard_generator.py` — Generate Grafana dashboards
   - `health_check_validator.py` — Validate service health checks
3. Use templates in `assets/templates/` (Prometheus alerts, OTel configs, runbooks)
4. Reference guides in `references/` for deep-dive topics
