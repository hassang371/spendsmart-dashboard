---
description: how to systematically debug issues using 4-phase root cause analysis
---

# Systematic Debugging

## When to Use

Use for ANY technical issue: test failures, bugs, unexpected behavior, performance problems, build failures, integration issues.

**Especially when:** under time pressure, "just one quick fix" seems obvious, you've already tried multiple fixes, or you don't fully understand the issue.

## Core Principle

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

## Process

1. **Load the FULL systematic-debugging skill folder** (Skill Loading Protocol):
   - `list_dir` on `.agents/skills/systematic-debugging/`
   - `view_file` on `SKILL.md` AND every file in `references/`, `scripts/`, `evals/`
2. Follow its structured phases: Root Cause → Pattern Analysis → Hypothesis Testing → Implementation
3. After fix is verified, output results to `walkthrough.md` artifact

## Red Flags — Return to Phase 1 If:

- You're proposing fixes before tracing data flow
- You've tried 3+ fixes without success (question architecture)
- You said "just try changing X and see if it works"
