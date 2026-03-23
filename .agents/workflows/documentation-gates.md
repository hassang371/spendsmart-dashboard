---
description: Non-negotiable documentation obligations — read at session start. Defines the 5 gates that govern investigation, design docs, spec review, commits, and implementation sync.
---

# Documentation Gates

**The law: No code without a design doc. No doc without spec review. No fix/feat commit without a Refs: line.**

These are gates, not guidelines. Each blocks the next step until satisfied.

---

## Gate 1: Discovery Gate (fires during investigation)

When investigating, researching, or analysing code and you find a defect, broken pipeline, missing data, or dead code:

1. **STOP** — do not discuss solutions, do not continue analysis, do not propose improvements
2. Create `docs/bugs/BUG-NNN-name.md` immediately (design-docs skill)
3. Run spec review on it (read `spec-review.md` and work through its checklists)
4. Commit: `git commit -m "docs: add BUG-NNN — <name>"`
5. Only then return to investigation or proceed to brainstorm the fix

**This gate fires even if no code is about to be written.**

Unconfirmed observations → `docs/investigations/<scratch-note>.md` (lightweight, unreviewed, never formal docs). Once confirmed, they graduate to proper Bug Reports.

**Investigation output contract:**
- Confirmed defect → `BUG-NNN` doc committed before discussing solutions
- Unconfirmed observation → scratch note in `docs/investigations/`
- Missing feature noticed → note only; create Feature LLD only if user confirms

---

## Gate 2: Design Gate (fires before any code change)

Before writing any code:

1. Is there a committed design doc (`docs/features/NNN`, `docs/bugs/BUG-NNN`, or `docs/rfcs/RFC-NNN`)?
2. Has spec review been run and passed?
3. Has the user approved the doc?

If any answer is NO → do not write code. Go back and satisfy the missing gate.

---

## Gate 3: Spec Review Gate (fires after writing or updating any doc)

After creating or updating ANY doc (Feature LLD, Bug Report, RFC, HLD, Policy):

1. Read `request-code-review.md` and apply it to the doc content
2. Fix all issues found
3. Re-run until no issues remain (max 3 iterations; surface to user if still failing)
4. Only commit the doc after spec review passes

**No exceptions for "small" updates.** The review for a minor update is fast — the discipline is the point.

**Review focus by doc type:**

| Doc type | Key checks |
|---|---|
| Bug Report | Root cause backed by code evidence (file + line)? Steps reproducible? Fix names exact files/functions? |
| Feature LLD | Success criteria are measurable checkboxes? All required sections filled? Security section non-empty? |
| HLD | Accurate against codebase right now? No phantom endpoints or tables? Diagrams agree with actual code? |
| RFC | Alternatives genuine (not strawmen)? Impact fully assessed? Decision clearly stated? |
| Policy | Rules actionable (not vague)? Examples provided? Enforcement mechanism described? |

---

## Gate 4: Commit Gate (fires before every fix: or feat: commit)

Every `fix:` commit MUST have: `Refs: docs/bugs/BUG-NNN-name.md`
Every `feat:` commit MUST have: `Refs: docs/features/NNN-name.md` (or RFC)

A commit without a `Refs:` line for these prefixes is an **orphan commit** and is not allowed.
If no doc exists, stop and create it first.

---

## Gate 5: Implementation Sync Gate (fires before verification)

Before running the verification suite, re-read the design doc and check:

- Did implementation deviate from the documented design?
- If YES: add a `DEVIATION:` entry to the doc changelog explaining what changed and why
- If NO: add a confirmation entry: `Implementation matches design. Status → Implemented`

Commit this doc update before running verification. Never verify against a stale doc.

---

## Quick Reference

```
Investigation finds defect
  → Gate 1: Create BUG-NNN + spec review + commit → THEN brainstorm fix

About to write code
  → Gate 2: Design doc exists + spec review passed + user approved?

Writing/updating a doc
  → Gate 3: Run spec review before committing

About to commit fix:/feat:
  → Gate 4: Refs: line present and pointing to a real file?

About to run verification
  → Gate 5: LLD re-read + deviations recorded?
```

---

## Trivially Scoped Bypass (Gates 1–3 only)

May bypass ONLY for changes that are ALL of:
- Single misspelled word, string literal, or comment
- No logic change
- No behavioral impact
- Single file

If you are asking whether it qualifies, it does not.
