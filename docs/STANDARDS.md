# SCALE Documentation Standards

> **Canonical source of truth for all agents (Claude, Gemini) and humans.**
> When any agent's internal doc-standards file conflicts with this file, this file wins.
> Last Updated: 2026-03-08

---

## Doc Types

| Type | Location | Naming | Auto-numbered |
|---|---|---|---|
| Feature LLD | `docs/features/` | `NNN-kebab-name.md` | Yes (001, 002…) |
| Bug Report | `docs/bugs/` | `BUG-NNN-kebab-name.md` | Yes (BUG-001…) |
| RFC (full) | `docs/rfcs/` | `RFC-NNN-kebab-name.md` | Yes (RFC-001…) |
| RFC (short) | `docs/rfcs/` | `RFC-NNN-kebab-name.md` | Yes (RFC-001…) |
| HLD (living) | `docs/design/` | `kebab-name.md` | No |
| Policies | `docs/policies/` | `kebab-name.md` | No |

**`docs/adr/` is deprecated.** All decisions (large or small) go in `docs/rfcs/`. Use full RFC for significant changes, short-form RFC for small decisions.

---

## Required Metadata Block

Every doc must open with a metadata block immediately after the title:

```markdown
> **Doc ID:** NNN-kebab-name
> **Date:** YYYY-MM-DD
> **Status:** [see lifecycle below]
> **DRI:** [Name — Directly Responsible Individual]
```

Additional fields by doc type:

| Type | Extra fields |
|---|---|
| Feature LLD | `Type: Feature LLD` |
| Bug Report | `Severity: Critical \| High \| Medium \| Low` |
| RFC (full) | `OKR Alignment: [which objective this serves]` |
| HLD | `Last Updated: YYYY-MM-DD`, `Version: 1.x` |

---

## Status Lifecycle

### Feature LLD
`Draft` → `Proposed` → `Approved` → `In Progress` → `Implemented` → `Verified`

### Bug Report
`Investigating` → `Root Cause Found` → `In Progress` → `Fix Applied` → `Verified`

### RFC
`Draft` → `Proposed` → `Approved` → `In Progress` → `Implemented` → `Verified` | `Rejected` | `Superseded`

### HLD
`Current` | `Outdated` | `Deprecated`

**Status update rule:** Update the doc status **before or alongside** the final implementation commit — never after.

| Code state | Doc status to set |
|---|---|
| Implementation committed | `Implemented` |
| Verification passed (tests green, evidence confirmed) | `Verified` |

---

## Required Sections Per Doc Type

### Feature LLD (all required)
1. Problem Statement
2. Success Criteria (measurable, checkboxes)
3. Scope — In Scope / Out of Scope
4. Design (architecture/data flow + at least 1 Mermaid diagram)
5. API Changes (if any)
6. Database Changes (if any)
7. Edge Cases & Error Handling
8. Security Considerations
9. Testing Strategy
10. Related Documents (HLD links, RFC links)

### Bug Report (all required)
1. Observed Behavior (exact error messages / logs)
2. Expected Behavior
3. Steps to Reproduce
4. Environment (branch, component, trigger)
5. Root Cause Analysis (with Mermaid diagram showing bug path)
6. Fix Description (files changed + why it works)
7. Regression Prevention (test added, guard added)
8. Related Documents

### RFC — Full (all required)
1. Problem Statement
2. Proposed Solution (with before/after Mermaid diagrams)
3. Detailed Design
4. Alternatives Considered (≥2, with rejection rationale)
5. Impact Assessment (what changes, what breaks, migration strategy)
6. Success Metrics
7. Timeline
8. Decision (approved/rejected/deferred + rationale)
9. Related Documents

### RFC — Short (for small decisions, all required)
1. Problem Statement (1–3 sentences)
2. Decision (what was chosen and why)
3. Alternatives Considered (1–2, brief)
4. Impact (what changes as a result)

### HLD — Living Document (all required)
1. Overview
2. Architecture/ER/Deployment Diagrams (≥3)
3. Domain/Module/Endpoint Details
4. Key Decisions
5. Changelog (append-only, newest at top)

---

## Mermaid Diagram Requirements

| Doc Type | Minimum | Preferred type |
|---|---|---|
| Feature LLD | 1 | Sequence (API flows) or Activity (business logic) |
| Bug Report | 1 | Sequence showing the bug's data path |
| RFC (full) | 2 | Current state architecture + proposed state |
| RFC (short) | 0 | Optional |
| HLD | 3+ | Architecture + data flow + deployment |

**All diagrams must:**
- Use Unicode symbols (🔐 🌐 ⚙️ 💾 📬 👤)
- Use descriptive labels — `"Auth Service (JWT)"` not `"Service A"`
- Use high-contrast, accessible colors

---

## Naming Conventions

| Type | Pattern | Example |
|---|---|---|
| Feature LLD | `NNN-kebab.md` (3-digit zero-padded) | `003-transaction-search.md` |
| Bug Report | `BUG-NNN-kebab.md` | `BUG-002-duplicate-ingestion.md` |
| RFC | `RFC-NNN-kebab.md` | `RFC-002-multi-currency.md` |
| HLD | `system-component.md` | `api-design.md` |
| Policy | `topic-policy.md` | `migration-policy.md` |

---

## Writing Style

1. **Be specific** — "Increases latency by ~200ms" not "might be slower"
2. **Show data flow** — How data enters, transforms, and exits
3. **Name things** — Concrete function/table/endpoint names, not abstractions
4. **No TODOs** — Every section filled. If unknown, write "TBD by [date/person]"
5. **Use diagrams** — A picture is worth a thousand tokens
6. **Version awareness** — Reference specific versions, commits, or dates

---

## HLD Sync Rule

After writing any Feature LLD or Bug Report, always check if an HLD needs updating:

| Change type | HLD to update |
|---|---|
| New or modified API endpoints | `docs/design/api-design.md` |
| Schema / DB changes | `docs/design/database-design.md` |
| Architecture / service topology | `docs/design/system-architecture.md` |

Add a changelog entry at the bottom of any HLD you update.
