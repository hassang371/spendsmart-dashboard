---
description: docs-driven development — the master workflow for building features, fixing bugs, and making architectural decisions
---

# Docs-Driven Development

## Overview

Every code change starts with documentation and ends with a version update. This master workflow orchestrates the full development lifecycle.

**Iron Rule:** Brainstorm → Document → Plan → Execute → Verify → Commit. In that order. Always.

## When to Use

Use this workflow for ANY of:

- Building a new feature
- Fixing a bug
- Making an architectural decision
- Any work that changes code
- Also fires when investigation reveals a defect — see Phase 0

## The Pipeline

```
Phase 0: Investigate  →  discovery gate (fires when defect found during research)
Step 1: Brainstorm    →  brainstorm.md (no round limit)
Step 2: Document      →  design-docs skill (LLD / bug report / RFC) + SPEC REVIEW
Step 3: Plan          →  write-plan.md
Step 4: Execute       →  tdd.md + execute-plan.md
Step 4.5: Doc Sync    →  re-read LLD, record deviations, update changelog
Step 5: Version Update →  verify.md + commit + push + Linear
```

---

## Phase 0: Investigation (fires when research reveals a defect)

This phase fires DURING any research or investigation task — not only when code is about to change.

**If you find a defect during investigation:**

1. **STOP** — do not continue the analysis, do not discuss solutions, do not propose fixes
2. Immediately create the Bug Report (`docs/bugs/BUG-NNN-name.md`) via the design-docs skill
3. Run **spec review** on the bug report (read `request-code-review.md` and apply to the doc)
4. Commit the bug report: `git commit -m "docs: add BUG-NNN — <name>"`
5. Only THEN proceed to Step 1 (Brainstorm the fix)

**Investigation output contract:**

Every investigation concludes with a structured output:
- Findings summary
- For each confirmed defect: a `BUG-NNN` doc committed (before discussing solutions)
- For each suspected issue (not yet confirmed): a note in `docs/investigations/` (lightweight, unreviewed)
- For each missing feature identified: note only — create Feature LLD only if user confirms to build it

`docs/investigations/` is a scratch directory for unreviewed findings. Notes here graduate to proper
`docs/bugs/` or `docs/features/` once confirmed. They are never committed as formal docs.

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

**Every doc requires a Changelog section** (Feature LLDs, Bug Reports, RFCs, Policies, HLDs).
Add an entry when the doc is first created and whenever the implementation deviates from the
original design. See `docs/STANDARDS.md` for changelog format per doc type.

**Run spec review before committing:**
After writing the doc, read `request-code-review.md` and apply it to the doc content. Fix all issues. Re-run until no issues remain (max 3 iterations; surface to user if still failing). No commit until spec review passes.

**Commit docs before any code:**

```
git add docs/
git commit -m "docs: add LLD for <name>"
```

**Exit criteria:** User approves the documentation AND spec review passes.

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
- **Mandatory `Refs:` line** for `fix:` and `feat:` commits — no exceptions:

```
fix: write user_model_metadata after adapter training

Upserts user_model_metadata on training completion so the classifier
can discover the adapter URL on next request.
Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md
```

```
feat: add transaction categorization confidence filter

Implements confidence threshold filtering for the categorization pipeline.
Refs: docs/features/002-confidence-filter.md
```

**No Refs: = orphan commit.** A `fix:` or `feat:` commit with no `Refs:` line is NOT ALLOWED. Create the doc first.
`refactor:`, `test:`, `chore:`, `docs:` commits: `Refs:` is optional but recommended.

- **Rule:** Before final implementation commit → update doc metadata `**Status:** Implemented`
- Status update must happen before or alongside the commit, never after

---

## Step 4.5: Implementation Doc Sync (before Version Update)

Before running verification, re-read the design doc and reconcile it against what was actually built.

**Check for deviations:**
- Did you use a different storage path, table name, or approach than the doc specifies?
- Did you add or remove something from scope during execution?
- Did you discover something that changes the design?

**If yes — update the doc changelog with a Deviation entry:**

```markdown
| YYYY-MM-DD | DEVIATION: [what changed from the design] — [why it changed] |
```

**If no deviations** — add a confirmation entry:

```markdown
| YYYY-MM-DD | Implementation matches design. Status → Implemented |
```

Commit the doc update before running verification.

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
