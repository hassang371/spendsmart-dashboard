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

1. **Load the FULL k8s-troubleshooter skill folder** (Skill Loading Protocol):
   - `list_dir` on `.agents/skills/k8s-troubleshooter/`
   - `view_file` on `SKILL.md` AND every file in `references/`, `scripts/`
2. Use diagnostic scripts and reference guides as discovered
