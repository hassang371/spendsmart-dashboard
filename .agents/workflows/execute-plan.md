---
description: how to execute an implementation plan in batches with review checkpoints
---

# Executing Plans

## Overview

Load plan from `task.md`, review critically, execute tasks in batches, report for review between batches.

**Core principle:** Batch execution with checkpoints for review.

## The Process

### Step 1: Load and Review Plan

1. Read `task.md` artifact
2. Review critically — identify questions or concerns
3. If concerns: Use `notify_user` to raise them before starting
4. If no concerns: Proceed

### Step 2: Execute Batch

**Default: First 3 tasks**

For each task:

1. Mark as `[/]` in `task.md`
2. Follow each step exactly (plan has bite-sized steps)
3. Run verifications as specified
4. Mark as `[x]` in `task.md`
5. Update `task_boundary` with progress

### Step 3: Report

When batch complete, use `notify_user`:

- Show what was implemented
- Show verification output
- Say: "Ready for feedback on this batch."

### Step 4: Continue

Based on feedback:

- Apply changes if needed
- Execute next batch
- Repeat until complete

### Step 5: Complete

After all tasks complete and verified:

- Write results to `walkthrough.md` artifact
- Use `verify.md` workflow for final verification

## When to Stop and Ask

**STOP executing immediately when:**

- Hit a blocker (missing dependency, test fails unexpectedly)
- Plan has critical gaps
- You don't understand an instruction
- Verification fails repeatedly

**Use `notify_user` for clarification rather than guessing.**

## Remember

- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Between batches: report and wait for feedback
- Stop when blocked, don't guess
