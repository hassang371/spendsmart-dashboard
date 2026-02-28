---
description: how to checkpoint context state during long sessions to prevent information loss
---

# Context Checkpoint

## Overview

Long conversations lose critical details as context grows. Checkpointing writes structured state to disk so it can be recovered.

**Core principle:** Write state before you need it. Don't wait until context is lost.

## When to Checkpoint

- Every 5 user turns in a conversation
- Before starting a complex multi-step task
- After completing a major milestone
- When context feels "long" (you're losing track of what's been done)
- When the anti-drift self-check triggers (every 3rd turn, check if checkpoint needed)

## The Checkpoint Process

### Step 1: Write State to `.gemini/current_state.md`

Use this exact structure:

```markdown
# Session State

## Phase

[Current phase: PLANNING / EXECUTION / VERIFICATION]

## Session Intent

[One sentence: what the user is trying to accomplish]

## Decisions Made

- [Decision 1 and rationale]
- [Decision 2 and rationale]

## Files Modified This Session

- [file path]: [what changed]
- [file path]: [what changed]

## Files Read (Important Context)

- [file path]: [why it matters]

## Current Status

- [What's done]
- [What's in progress]
- [What's blocked]

## Next Steps

1. [Immediate next action]
2. [Following action]

## Key Facts to Remember

- [Specific error messages, test counts, config values — anything you'd need to re-fetch if lost]
```

### Step 2: Update `task.md`

Mark completed items `[x]`, in-progress items `[/]`. This is your second line of defense — if `current_state.md` isn't enough, `task.md` has the full checklist.

### Step 3: Resume

On the next turn, if context feels thin:

1. Read `.gemini/current_state.md`
2. Read `task.md`
3. Continue from where you left off

## What to Preserve (Signal)

- User's original intent and requirements
- Specific error messages and codes
- File paths modified and what changed
- Decisions made and their rationale
- Test results (counts, pass/fail)
- Config values and environment details

## What to Discard (Noise)

- Exploration that led nowhere
- Verbose tool output already processed
- Back-and-forth clarification that's been resolved
- Intermediate debugging steps after root cause found

## Recovery Pattern

If you find yourself confused about what's been done:

```
1. READ .gemini/current_state.md
2. READ task.md artifact
3. If still unclear, list modified files:
   git diff --stat (if git is available)
4. If still unclear, ask the user for a quick recap
```

## Integration with Anti-Drift

The Global Rule's self-check (every 3 turns) includes:

> "Should I checkpoint context?"

If the conversation is 10+ turns, the answer is YES. Read this workflow and execute the checkpoint.

## Key Insight

Checkpointing costs ~30 seconds. Losing context costs minutes of re-exploration. **Always checkpoint when in doubt.**
