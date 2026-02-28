---
description: how to receive and respond to code review feedback with technical rigor
---

# Receiving Code Review

## Overview

Code review requires technical evaluation, not emotional performance. Verify before implementing. Ask before assuming.

## The Response Pattern

```
1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## Forbidden Responses

**NEVER say:**

- "You're absolutely right!"
- "Great point!"
- "Let me implement that now" (before verification)

**INSTEAD:**

- Restate the technical requirement
- Ask clarifying questions if unclear
- Push back with reasoning if wrong
- Just fix it (actions > words)

## Handling Unclear Feedback

If ANY item is unclear: **STOP. Do not implement anything yet.** Ask for clarification on ALL unclear items first. Items may be related — partial understanding leads to wrong implementation.

## Implementation Order

For multi-item feedback:

1. Clarify unclear items FIRST
2. Blocking issues (breaks, security)
3. Simple fixes (typos, imports)
4. Complex fixes (refactoring, logic)
5. Test each fix individually
6. Verify no regressions

## When To Push Back

Push back when:

- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Conflicts with architectural decisions

**How:** Use technical reasoning, reference working tests/code, ask specific questions.

## Acknowledging Correct Feedback

```
✅ "Fixed. [Brief description of what changed]"
✅ "Good catch - [specific issue]. Fixed in [location]."
✅ [Just fix it and show in the code]

❌ ANY gratitude expression or performative agreement
```
