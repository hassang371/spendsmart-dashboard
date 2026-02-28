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

Run the command. Read the output. THEN claim the result.
Save evidence to `walkthrough.md`. Non-negotiable.
