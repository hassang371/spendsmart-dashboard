---
description: how to verify work before claiming completion
---

# Verification Before Completion

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## Pre-Verification: Implementation Doc Sync (Gate 5)

Before running any verification checks, complete this first:

1. Re-read the design doc (LLD/RFC/Bug Report) for this work
2. Did implementation deviate from the documented design?
   - **If YES** → add a `DEVIATION:` entry to the doc changelog + commit the update
   - **If NO** → add confirmation entry: `Implementation matches design. Status → Implemented` + commit
3. Only then proceed to the verification checklist below

Never verify against a stale doc.

---

## The Gate Function

```
BEFORE claiming any status:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim
6. DOCUMENT: Save verification results to walkthrough.md artifact

Skip any step = lying, not verifying
```

## Structured Validation Checklist

Before claiming completion, verify ALL applicable items:

### Code Quality

- [ ] All tests pass (run command, show output)
- [ ] Build succeeds (run command, show output)
- [ ] No new linting errors introduced

### Requirements

- [ ] All acceptance criteria from the LLD are met (line-by-line check)
- [ ] Edge cases from the design are handled
- [ ] Error scenarios work as specified

### Documentation

- [ ] Feature LLD exists in `docs/features/`
- [ ] HLD updated if design-docs skill's sync protocol requires it
- [ ] Code is self-documenting (no unexplained magic)

### Regression

- [ ] Existing tests still pass
- [ ] No unintended side effects in adjacent features

## 4-Level Verdict

After running the checklist, issue ONE verdict:

| Verdict      | Meaning                            | Action                                 |
| ------------ | ---------------------------------- | -------------------------------------- |
| **PASS**     | All checks pass, evidence provided | Proceed to commit/completion           |
| **CONCERNS** | Passes but with minor issues noted | Flag concerns, proceed if non-blocking |
| **REWORK**   | One or more checks fail            | Return to implementation, fix issues   |
| **FAIL**     | Fundamental design flaw discovered | Return to planning/brainstorming       |

## Common Failures

| Claim            | Requires                        | Not Sufficient                |
| ---------------- | ------------------------------- | ----------------------------- |
| Tests pass       | Test command output: 0 failures | Previous run, "should pass"   |
| Build succeeds   | Build command: exit 0           | Linter passing                |
| Bug fixed        | Test original symptom: passes   | "Code changed, assumed fixed" |
| Requirements met | Line-by-line checklist          | "Tests passing"               |

## Red Flags — STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Done!")
- About to commit/push without verification
- Relying on partial verification
- **ANY wording implying success without verification**

## Rationalization Prevention

| Excuse                    | Reality                |
| ------------------------- | ---------------------- |
| "Should work now"         | RUN the verification   |
| "I'm confident"           | Confidence ≠ evidence  |
| "Just this once"          | No exceptions          |
| "Partial check is enough" | Partial proves nothing |

## When To Apply

**ALWAYS before:**

- ANY success/completion claim
- ANY expression of satisfaction
- Committing, PR creation, task completion
- Moving to next task
- Using `notify_user` to report completion

## The Bottom Line

Run the command. Read the output. Issue a verdict. Save evidence to `walkthrough.md`. Non-negotiable.
