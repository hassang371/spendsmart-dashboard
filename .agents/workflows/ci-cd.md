---
description: CI/CD pipeline design, optimization, DevSecOps security scanning, and troubleshooting. Use for creating workflows, debugging pipeline failures, implementing SAST/DAST/SCA, optimizing build performance, implementing caching strategies, setting up deployments, securing pipelines with OIDC/secrets management, and troubleshooting common issues across GitHub Actions, GitLab CI, and other platforms.
---

# CI/CD Pipelines

## When to Use

Use for ANY CI/CD pipeline work:

- Creating GitHub Actions or GitLab CI workflows
- Optimizing build performance and caching
- Implementing DevSecOps security scanning
- Debugging pipeline failures
- Setting up deployment strategies
- Securing pipelines (OIDC, secrets management)

## Process

1. **Read** `.agents/skills/ci-cd/SKILL.md` for the full framework
2. Use ready-made templates in `assets/templates/`:
   - `github-actions/` — Node, Python, Go, Docker, Security scan workflows
   - `gitlab-ci/` — Equivalent GitLab CI templates
3. Use scripts: `pipeline_analyzer.py`, `ci_health.py`
4. Reference guides for optimization, security, DevSecOps, troubleshooting
