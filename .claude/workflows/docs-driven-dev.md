---
description: Master workflow for building features, fixing bugs, and making architectural decisions in SCALE. Load this file whenever a code change is planned.
---

# Docs-Driven Development (Claude-Native)

## Overview

Every code change starts with brainstorming, followed by documentation, then implementation. No code without a design doc. No completion without verification.

**Iron Rule:** Brainstorm → Document → Plan → Execute → Verify → Commit. In that order. Always.

## When to Use

For ANY of: new feature, bug fix, architectural decision, or any work that changes code.

## The Pipeline

```
Step 1: Brainstorm  →  superpowers:brainstorming (no round limit)
Step 2: Document    →  design-docs skill (LLD / bug report / RFC)
Step 3: Plan        →  superpowers:writing-plans
Step 4: Execute     →  superpowers:test-driven-development + superpowers:executing-plans
Step 5: Verify      →  superpowers:verification-before-completion
Step 6: Commit      →  Conventional commits + HLD sync check
```

---

## Step 1: Brainstorm

**Invoke:** `superpowers:brainstorming` via Skill tool

- Run for **as many rounds as the user needs** — no fixed limit
- Do NOT rush or shortcut this step
- Exit criteria: user explicitly says they are satisfied with the direction

**Note:** Brainstorming IS this step. Do not brainstorm separately and then start the workflow — they are the same thing.

---

## Step 2: Document

**Invoke:** Read `.claude/skills/design-docs/SKILL.md` then follow its process

Based on work type:

| Work Type    | Create |
|---|---|
| New feature  | `docs/features/NNN-name.md` (feature LLD) |
| Bug fix      | `docs/bugs/BUG-NNN-name.md` (bug report) |
| Big decision | `docs/rfcs/RFC-NNN-name.md` (RFC) |
| System doc   | `docs/design/*.md` (HLD update) |

Must include at least one Mermaid diagram. HLD sync check required after every LLD.

**Every doc requires a Changelog section** (Feature LLDs, Bug Reports, RFCs, Policies, HLDs).
Add an entry when the doc is first created and whenever the implementation deviates from the
original design. See `docs/STANDARDS.md` for changelog format per doc type.

**Commit docs before any code:**

```bash
git add docs/
git commit -m "docs: add LLD for <name>"
```

Exit criteria: user approves the documentation.

---

## Step 3: Plan

**Invoke:** `superpowers:writing-plans` via Skill tool

- Reference the LLD doc from Step 2
- Plan = `TaskCreate` entries (one per task) — do NOT create `implementation_plan.md` or any plan file
- Exit criteria: user approves the plan

---

## Step 4: Execute

**Invoke:** `superpowers:test-driven-development` then `superpowers:executing-plans` or `superpowers:subagent-driven-development`

- RED → GREEN → REFACTOR on every task
- `TaskCreate` entries for each task, update status as you go
- Commit after each logical unit:

| Prefix | When |
|---|---|
| `feat:` | New feature implementation |
| `fix:` | Bug fix |
| `test:` | Adding/updating tests |
| `refactor:` | Code restructuring, no behavior change |
| `chore:` | Maintenance, config, HLD sync |

---

## Step 5: Verify

**Invoke:** `superpowers:verification-before-completion`

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

---

## Step 6: Final Commit

1. Update design doc status to `Implemented` (if not already `Verified`)
2. Re-check HLD sync: did implementation deviate from the design doc?
3. Update affected `docs/design/*.md` + add changelog entries
4. Final commit: `chore: update HLD and finalize <feature-name>`

---

## Transition Rules

| From | To | Trigger |
|---|---|---|
| Brainstorm | Document | User says they're satisfied |
| Document | Plan | User approves docs |
| Plan | Execute | User approves plan |
| Execute | Verify | All tasks complete |
| Verify PASS | Final Commit | Evidence confirmed |
| Verify FAIL | Execute (retry) | Fix issues, re-verify |
| Any step | Brainstorm | Fundamental flaw discovered |
