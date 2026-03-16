# Documentation Gate

This rule is auto-loaded on every session. It defines the non-negotiable documentation
obligations that apply at every stage of work.

---

## The Law

**No code change without a design doc. No discussion of solutions without a bug/feature doc.
No doc without a spec review. No fix/feat commit without a Refs: line.**

These are not guidelines. They are gates. Each one blocks the next step until satisfied.

---

## Gate 1: Discovery Gate (fires during investigation)

When you are investigating, researching, or analysing code and you find:
- A defect, broken pipeline, missing data, or dead code
- A constraint violation, wrong path, or unreachable state

**You must:**
1. STOP — do not discuss solutions, do not continue analysis, do not propose improvements
2. Create `docs/bugs/BUG-NNN-name.md` immediately (design-docs skill)
3. Run spec review on it (`superpowers:code-reviewer`)
4. Commit the bug report: `git commit -m "docs: add BUG-NNN — <name>"`
5. Only then return to investigation or proceed to brainstorm the fix

**This gate fires even if no code is about to be written.**

Unconfirmed observations go to `docs/investigations/<scratch-note>.md` (lightweight, unreviewed,
never committed as formal docs). Once confirmed, they graduate to proper Bug Reports.

---

## Gate 2: Design Gate (fires before any code change)

Before writing any code for a feature or bug fix:

1. Is there a committed design doc (`docs/features/NNN`, `docs/bugs/BUG-NNN`, or `docs/rfcs/RFC-NNN`)?
2. Has spec review been run and passed on that doc?
3. Has the user approved the doc?

If any answer is NO → do not write code. Go back and satisfy the missing gate.

---

## Gate 3: Spec Review Gate (fires after writing or updating any doc)

After creating or updating ANY doc (Feature LLD, Bug Report, RFC, HLD, Policy):

1. Dispatch `superpowers:code-reviewer` with the doc content + type + review focus
2. Fix all issues found
3. Re-dispatch until no issues remain (max 3 iterations; surface to user if still failing)
4. Only commit the doc after spec review passes

**No exceptions for "small" updates.** Adding a changelog entry to an HLD still requires
a review pass. The review for a minor update is fast — the discipline is the point.

---

## Gate 4: Commit Gate (fires before every fix: or feat: commit)

Every `fix:` commit must have: `Refs: docs/bugs/BUG-NNN-name.md`
Every `feat:` commit must have: `Refs: docs/features/NNN-name.md` (or RFC)

A commit without a `Refs:` line for these prefixes is an **orphan commit** and is not allowed.
If no doc exists, stop and create it first.

---

## Gate 5: Implementation Sync Gate (fires before verification)

Before running the verification suite (Step 5), re-read the design doc and check:

- Did implementation deviate from the documented design?
- If YES: add a `DEVIATION:` entry to the doc changelog explaining what changed and why
- If NO: add a confirmation entry: `Implementation matches design. Status → Implemented`

Commit this doc update before running verification. Never verify against a stale doc.

---

## Quick Reference

```
Investigation finds defect
  → Gate 1: Create BUG-NNN + spec review + commit
  → THEN brainstorm the fix

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

## What "Trivially Scoped" Means (bypass for Gates 1–3)

Gates 1–3 may be bypassed ONLY for changes that are ALL of:
- Single misspelled word, string literal, or comment
- No logic change
- No behavioral impact
- Single file

If you are asking whether it qualifies, it does not.
