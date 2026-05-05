---
description: Master workflow for building features, fixing bugs, and making architectural decisions in SCALE. Load this file whenever a code change is planned.
---

# Docs-Driven Development (Claude-Native)

## Overview

Every code change starts with brainstorming, followed by documentation, then implementation. No code without a design doc. No completion without verification.

**Iron Rule:** Brainstorm → Document → Plan → Execute → Verify → Commit. In that order. Always.

This workflow is intentionally written in **situation language**, not skill names. The
binding from situation → skill is in `.claude/skills-registry.md`. Future plugin changes
update the registry; this workflow stays stable.

## When to Use

For ANY of: new feature, bug fix, architectural decision, or any work that changes code.
Also fires when investigation reveals a defect — see Phase 0.

## The Pipeline

```
Phase 0: Investigate  →  Discovery Gate (fires when defect found during research)
Step 1: Brainstorm    →  interview-style grilling (registry: brainstorm situation)
Step 2: Document      →  design-docs skill (LLD / Bug Report / ADR) + SPEC REVIEW
Step 3: Plan          →  registry: plan-writing situation (saved to docs/plans/)
Step 4: Execute       →  registry: TDD execution + plan execution (vertical slicing)
Step 4.5: Doc Sync    →  re-read design doc, record deviations, update changelog
Step 5: Self review   →  registry: code self-review situation (terse, line-by-line)
Step 5.5: Adversarial →  OPTIONAL — registry: adversarial-review situation (Codex)
Step 6: Verify        →  registry: verification situation. Bugs require user confirmation.
Step 7: Commit        →  Conventional commits + Refs: line + Design Doc sync check
```

---

## Phase 0: Investigation (fires when research reveals a defect)

This phase fires DURING any research or investigation task — not only when code is about to change.

**If you find a defect during investigation:**

1. **STOP** — do not continue the analysis, do not discuss solutions, do not propose fixes
2. Immediately create the Bug Report (`docs/bugs/BUG-NNN-name.md`) via the design-docs skill
3. Run **spec review** on the bug report (registry: spec-review situation)
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

**Promotion path:** When investigation confirms a defect → graduate scratch note to BUG-NNN
immediately. Delete or archive the scratch note. See `documentation-gate.md` Gate 1.

---

## Step 1: Brainstorm

**Situation:** project-aware interview-style grilling.

- Run for **as many rounds as the user needs** — no fixed limit
- Reads `CONTEXT.md` and `docs/adr/` so questions are grounded in actual project decisions
- Do NOT rush or shortcut this step
- Exit criteria: user explicitly says they are satisfied with the direction

**Note:** Brainstorming IS this step. Do not brainstorm separately and then start the workflow — they are the same thing.

---

## Step 2: Document

**Invoke:** Read `.claude/skills/design-docs/SKILL.md` then follow its process.

Based on work type:

| Work Type    | Create |
|---|---|
| New feature  | `docs/features/NNN-name.md` (Feature LLD) |
| Bug fix      | `docs/bugs/BUG-NNN-name.md` (Bug Report) |
| Architectural decision | `docs/adr/ADR-NNN-name.md` (ADR — recorded decision) |
| System component update | `docs/design/<component>.md` (Design Doc — living) |

Must include at least one Mermaid diagram for non-trivial designs. Design Doc sync check required after every Feature LLD.

**Every doc requires a Changelog section** (Feature LLDs, Bug Reports, ADRs, Policies, Design Docs).
Add an entry when the doc is first created and whenever the implementation deviates from the
original design. See `docs/STANDARDS.md` for changelog format per doc type.

**Run spec review before committing.** Fix all issues. No commit until spec review passes.

**Commit docs before any code:**

```bash
git add docs/
git commit -m "docs: add LLD for <name>"
```

Exit criteria: user approves the documentation AND spec review passes.

---

## Step 3: Plan

**Situation:** plan-writing for multi-step work.

- Reference the design doc from Step 2
- Plan saves to `docs/plans/YYYY-MM-DD-name.md` — never `docs/superpowers/specs/` or any plugin-specific path
- TaskCreate entries are also created from the plan, one per task
- Skip this step entirely for trivially-scoped or single-step changes
- Exit criteria: user approves the plan

**Pitfall — LLD vs Plan no-overlap:** Feature LLD describes WHAT to build. Plan describes HOW
and IN WHAT ORDER to build it. A plan that re-states the LLD's design content is doing the
wrong thing. A plan that introduces design decisions not in the LLD means the LLD is incomplete
— update the LLD first.

---

## Step 4: Execute

**Situation:** TDD execution.

- **Vertical slicing**: one test → one implementation → repeat. NOT all-tests-then-all-implementation (horizontal). Horizontal slicing produces tests that test imagined behavior, not actual.
- RED → GREEN → REFACTOR per slice
- Iron rule: NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
- TaskCreate entries for each slice, update status as you go
- Commit after each logical unit

| Prefix | When |
|---|---|
| `feat:` | New feature implementation (with `Refs: docs/features/...`) |
| `fix:` | Bug fix (with `Refs: docs/bugs/BUG-NNN-...` AFTER user confirms resolved) |
| `test:` | Adding/updating tests |
| `refactor:` | Code restructuring, no behavior change |
| `chore:` | Maintenance, config, Design Doc sync |
| `wip:` | Work-in-progress during bug iteration loops (no Refs: required) |

---

## Step 4.5: Implementation Doc Sync (before Verify)

Before running verification, re-read the design doc and reconcile it against what was actually built.

**Check for deviations:**
- Did you use a different storage path, table name, or approach than the doc specifies?
- Did you add or remove something from scope during execution?
- Did you discover something that changes the design?

**If yes — update the doc changelog with a Deviation entry:**

```markdown
| YYYY-MM-DD | DEVIATION: [what changed from the design] — [why it changed] |
```

This is distinct from a normal status-change entry. It records WHY reality diverged from intent.
This step is what prevents documents from becoming stale silently.

**If no deviations** — add a confirmation entry:

```markdown
| YYYY-MM-DD | Implementation matches design. Status → Implemented |
```

Commit the doc update before running verification.

---

## Step 5: Self review (terse, line-by-line)

**Situation:** code self-review before opening for verification.

Run a fast, comment-style review on your own diff. Fix nits, naming, dead code, missed edge
cases. The discipline is the point — first reviewer is yourself.

---

## Step 5.5: Adversarial review (OPTIONAL)

**Situation:** adversarial / second-opinion review.

Use this when:
- The change touches money-handling, auth, or data-loss-prone paths
- The change is large enough that a different model's perspective would catch blind spots
- You suspect the design has issues you can't see

A different model = different blind spots. Skip for trivially-scoped changes.

---

## Step 6: Verify

**Situation:** verification before claiming complete.

**Definition of Done — ALL must pass before claiming complete:**

| Check | Command |
|---|---|
| Backend tests | `.venv/bin/python -m pytest apps/ packages/ -v` |
| Frontend tests | `cd apps/web && npm run test` |
| TypeScript | `npx tsc --noEmit` |
| Lint | `cd apps/web && npm run lint` |

- Run each command and read the actual output — do not assume
- If ANY fail → back to Step 4
- If ALL pass → update the design doc status to `Verified`:

  ```
  docs: update <doc-id> status to Verified
  ```

### Bug iteration loop — user confirmation is the gate

For bug fixes, `make check` passing is necessary but **NOT sufficient**. The user must confirm
the bug is actually resolved.

If the user reports the bug still persists:
1. **Same BUG-NNN doc** — do NOT create a new one. One BUG-NNN per defect, lifetime spans iterations.
2. Append a new iteration entry to the BUG-NNN changelog: hypothesis tried, what was changed, observed result.
3. Loop back to Step 4 (Execute) with a new vertical slice.
4. NO `fix:` commit. Use `wip:` prefix during iteration.
5. Repeat until user explicitly confirms resolution.

When user confirms:
- Update BUG-NNN status to `Verified`
- Consolidate WIP work into one `fix:` commit (or squash) with `Refs: docs/bugs/BUG-NNN-name.md`

---

## Step 7: Final Commit

1. Update design doc status to `Implemented` (if not already `Verified`)
2. Re-check Design Doc sync: did implementation deviate from the design doc?
3. Update affected `docs/design/*.md` + add changelog entries
4. Final commit: `chore: update Design Doc and finalize <feature-name>`

---

## Transition Rules

| From | To | Trigger |
|---|---|---|
| Brainstorm | Document | User says they're satisfied |
| Document | Plan | User approves docs |
| Plan | Execute | User approves plan |
| Execute | Self review | Slice complete |
| Self review | Adversarial review | Optional, user choice |
| Self review / Adversarial | Verify | Reviews clean |
| Verify PASS | Final Commit | Evidence confirmed (user confirms for bugs) |
| Verify FAIL | Execute (retry) | Fix issues, re-verify, same doc |
| Any step | Brainstorm | Fundamental flaw discovered |
