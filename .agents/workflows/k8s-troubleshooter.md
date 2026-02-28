---
description: Systematic Kubernetes troubleshooting and incident response. Use when diagnosing pod failures, cluster issues, performance problems, networking issues, storage failures, or responding to production incidents. Provides diagnostic workflows, automated health checks, and comprehensive remediation guidance for common Kubernetes problems.
---

# Kubernetes Troubleshooting

## When to Use

Use for ANY Kubernetes issue:

- Pod failures (CrashLoopBackOff, OOMKilled, ImagePullBackOff)
- Cluster health problems
- Performance troubleshooting
- Networking and storage issues
- Production incident response

## Process

1. **Read** `.agents/skills/k8s-troubleshooter/SKILL.md` for the full diagnostic framework
2. Use bundled diagnostic scripts in `scripts/`:
   - `cluster_health.py` — Full cluster health check
   - `diagnose_pod.py` — Deep pod diagnostics
   - `check_namespace.py` — Namespace-level analysis
3. Reference guides for common issues, Helm troubleshooting, incident response, performance
