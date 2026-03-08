# docs/adr — Architecture Decision Records

> **Feature 002 Rec A1** — Introduced 2026-03-08

This `README.md` is the **directory index** (auto-rendered by GitHub/GitLab as the folder landing page).
It is **not** itself an ADR.

## File naming convention

| File | Purpose |
|---|---|
| `README.md` | This index — template, instructions, backlog (you are here) |
| `0001-auth-model.md` | First ADR |
| `0002-job-orchestration.md` | Second ADR |
| `NNNN-kebab-slug.md` | All ADRs follow this pattern |

Each ADR file is numbered sequentially, prefixed with four zero-padded digits, followed by a short kebab-case title.

---

## Template

```markdown
# ADR-NNNN: [Decision Title]

**Date:** YYYY-MM-DD  
**Status:** Proposed | Accepted | Superseded by ADR-NNNN  
**Deciders:** [names or roles]

## Context

What is the problem and what constraints are we operating under?

## Decision

What did we decide and why?

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| A      | ...  | ...  |
| B      | ...  | ...  |

## Consequences

- **Positive:** ...
- **Negative / Trade-offs:** ...
- **Risks:** ...

## Related

- Links to other ADRs, issues, or docs.
```

---

## Existing Implicit Decisions to Document

| ADR ID | Topic | Urgency |
|--------|-------|---------|
| ADR-0001 | Auth and tenant isolation model (Supabase RLS + explicit filters) | High |
| ADR-0002 | Job orchestration: Celery + Redis polling worker (not event-driven) | High |
| ADR-0003 | Forecasting approach: TFT via pytorch-forecasting + per-user fine-tune | High |
| ADR-0004 | Ingestion parsing strategy: BankStatementParser + dedup semantics | Medium |
| ADR-0005 | Cache layer: localStorage with env-prefix TTL (no server-side cache) | Medium |

## Enforcement

PRs that make architecture-impacting changes should reference an ADR.
Add a PR template check: "Does this PR require a new or updated ADR? [ ]"
