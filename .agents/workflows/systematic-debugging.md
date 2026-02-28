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

1. **Read** `.agents/skills/systematic-debugging/SKILL.md` for the full 4-phase debugging framework
2. Follow its structured phases: Root Cause → Pattern Analysis → Hypothesis Testing → Implementation
3. Use bundled tools:
   - `scripts/find-polluter.sh` — Find test pollution in test suites
   - `references/root-cause-tracing.md` — Backward tracing technique
   - `references/defense-in-depth.md` — Multi-layer validation after fix
   - `references/condition-based-waiting.md` — Replace sleep() with condition polling
4. After fix is verified, output results to `walkthrough.md` artifact

## Red Flags — Return to Phase 1 If:

- You're proposing fixes before tracing data flow
- You've tried 3+ fixes without success (question architecture)
- You said "just try changing X and see if it works"
