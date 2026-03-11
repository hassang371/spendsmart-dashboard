---
description: docs-driven development — the master workflow for building features, fixing bugs, and making architectural decisions
---

# Docs-Driven Development

## Overview

Every code change starts with documentation and ends with a version update. This master workflow orchestrates the full development lifecycle.

**Iron Rule:** No code without a design doc. No commit without documentation. No merge without verification.

## When to Use

Use this workflow for ANY of:

- Building a new feature
- Fixing a bug
- Making an architectural decision
- Any work that changes code

## The Pipeline

```
Step 1: Brainstorm (extensive, user-driven)
    ↓
Step 2: Document (LLD + update HLD)
    ↓
Step 3: Plan (Epic → Story → Task breakdown)
    ↓
Step 4: Execute (TDD — implement with tests)
    ↓
Step 5: Version Update (commit, push, update docs, update Linear)
```

---

## Step 1: Brainstorm

**Invoke:** `brainstorm.md` workflow

This step runs for **5-10+ rounds** of back-and-forth with the user. Do NOT rush.

**Exit criteria:** User explicitly says they are satisfied with the design direction.

---

## Step 2: Document

**Invoke:** `design-docs` skill — read `.agents/skills/design-docs/SKILL.md`, then follow its progressive disclosure (load only what SKILL.md directs, not the full folder)

Based on the work type:

| Work Type    | Action                                                             |
| ------------ | ------------------------------------------------------------------ |
| New feature  | Create `docs/features/NNN-name.md` using `feature-lld.md` template |
| Bug fix      | Create `docs/bugs/BUG-NNN-name.md` using `bug-report.md` template  |
| Big decision | Create `docs/rfcs/RFC-NNN-name.md` using `rfc.md` template         |

**Must include:**

- At least one Mermaid diagram
- All sections filled (no TODOs)
- HLD sync check (update `docs/design/*.md` if needed)

**Commit docs before code:**

```
git add docs/
git commit -m "docs: add LLD for <name>"
```

**Exit criteria:** User approves the documentation.

---

## Step 3: Plan

**Invoke:** `write-plan.md` workflow

Create implementation plan with Epic → Story → Task hierarchy.

- Reference the LLD doc created in Step 2
- Include diagrams in the plan where useful
- Save to `implementation_plan.md` and `task.md` artifacts

**Exit criteria:** User approves the plan.

---

## Step 4: Execute

**Invoke:** `execute-plan.md` → `tdd.md` workflows

Execute the plan following TDD (Red → Green → Refactor).

**Commit strategy during execution:**

- Commit after each logical unit: `feat:`, `fix:`, `test:`, `refactor:`
- Mid-feature commits are allowed if a sub-task is independently useful
- Always include the feature/bug doc number in commit body
- **Rule:** Before final implementation commit → update doc metadata `**Status:** Implemented`
- Status update must happen before or alongside the commit, never after

---

## Step 5: Version Update

After implementation and verification (using `verify.md`).

**Definition of Done — ALL must pass before claiming complete (SCALE-specific):**

| Check | Command |
|---|---|
| Backend tests (api + worker) | `.venv/bin/python -m pytest apps/ packages/ -v --tb=short` |
| Frontend tests | `cd apps/web && npm test -- --passWithNoTests` |
| TypeScript | `cd apps/web && npx tsc --noEmit` |
| Lint | `cd apps/web && npm run lint` |

Run each command and read the actual output — do not assume.

### 5a. Final Doc Sync

- Re-check HLD sync: did implementation change anything from the design?
- Update affected `docs/design/*.md` files
- Add changelog entries
- **Rule:** After verification passes → update doc metadata `**Status:** Verified`

### 5b. Final Commit

```
git add .
git commit -m "chore: update HLD and finalize <feature-name>"
```

### 5c. Push

```
git push
```

### 5d. Update Linear (if connected)

- Update the issue status to "Done"
- Add a comment with the LLD link and commit hash

---

## Commit Message Convention

| Prefix      | When                                    |
| ----------- | --------------------------------------- |
| `docs:`     | Documentation changes (LLD, HLD, RFC)   |
| `feat:`     | New feature implementation              |
| `fix:`      | Bug fix                                 |
| `test:`     | Adding/updating tests                   |
| `refactor:` | Code restructuring (no behavior change) |
| `chore:`    | Maintenance (deps, config, HLD sync)    |

---

## Transition Rules

| From       | To              | Trigger                                             |
| ---------- | --------------- | --------------------------------------------------- |
| Brainstorm | Document        | User says they're satisfied                         |
| Document   | Plan            | User approves documentation                         |
| Plan       | Execute         | User approves plan                                  |
| Execute    | Version Update  | `verify.md` returns PASS verdict                    |
| Execute    | Execute (retry) | `verify.md` returns REWORK verdict                  |
| Any step   | Brainstorm      | `verify.md` returns FAIL verdict (fundamental flaw) |
