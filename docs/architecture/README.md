# SCALE App — Architecture Documentation

## Purpose

This directory contains the complete architecture design for the SCALE App overhaul. These documents provide full context for any agent or developer working on the milestones.

## Document Index

| Document                                                             | Purpose                                                                                           | Read Before                     |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------- |
| [00_architecture_overview.md](00_architecture_overview.md)           | High-level architecture decisions, brainstorm results, key choices                                | All milestones                  |
| [01_system_design.md](01_system_design.md)                           | System design: NFRs, request lifecycle, load balancing, caching, database, failure modes, scaling | All milestones                  |
| [02_implementation_plan.md](02_implementation_plan.md)               | Detailed implementation plan with all files to create/modify/delete per milestone                 | The milestone you're working on |
| [03_devops_security_monitoring.md](03_devops_security_monitoring.md) | Deep-dive: Dockerfile, CI/CD, security middleware, rate limiting, structured logging, Sentry      | M3, M4, M5                      |
| [04_database_testing_sre.md](04_database_testing_sre.md)             | Deep-dive: Database optimization, testing strategy, SRE practices (SLOs, runbooks)                | M2, M6                          |
| [05_task_checklist.md](05_task_checklist.md)                         | Master task checklist with all milestones and bite-sized tasks                                    | All milestones                  |

## Milestone Quick Reference

| Milestone                                  | Focus                                            | Key Docs   | Dependencies |
| ------------------------------------------ | ------------------------------------------------ | ---------- | ------------ |
| **M1: Core Backend Restructure**           | Domain modules, bug fixes, frontend cleanup      | `02`, `01` | None         |
| **M2: API Design & Database Optimization** | OpenAPI, pagination, indexes, query optimization | `02`, `04` | M1           |
| **M3: Security Hardening**                 | Rate limiting, CORS, security headers, auth      | `02`, `03` | M1           |
| **M4: DevOps & CI/CD**                     | Docker, GitHub Actions, deployment               | `02`, `03` | M1           |
| **M5: Monitoring & Observability**         | Logging, Sentry, health checks, alerting         | `02`, `03` | M1, M4       |
| **M6: SRE Foundation**                     | SLOs, runbooks, chaos engineering, k6 load tests | `04`       | M5           |

## Skills Used

8 skills informed this design:
architecture-designer, api-designer, devops-engineer, monitoring-expert, secure-code-guardian, database-optimizer, sre-engineer, test-master

## Current Codebase Summary

- **Monorepo**: `apps/web` (Next.js 15), `apps/api` (FastAPI), `apps/worker` (Celery), `packages/` (shared Python)
- **Database**: Supabase (Postgres) — 2 tables (`transactions`, `training_jobs`) + RLS
- **Worker**: Celery with Redis broker, 2 replicas
- **15 known issues** from Codebase Audit: 4 critical bugs, 5 architectural flaws, 6 improvements needed
- **Key problem**: Next.js has 4 API routes doing heavy lifting (should be in FastAPI)
