---
description: introduction to the superpowers framework and how workflows integrate with Antigravity
---

# Using Superpowers

## Overview

Superpowers is a collection of workflows that enforce disciplined software development. The workflows live in `.agents/workflows/` and are invoked by the Global Rule or by `/` commands.

## The Core Loop

```
BEFORE any response or action:
  1. Does a workflow apply here? (Check activation map in Global Rule)
  2. If YES → Read the workflow file BEFORE responding
  3. If NO → Respond normally, but apply core principles (TDD, YAGNI, DRY)
```

## Available Workflows

### Process Workflows (prioritize these)

| Workflow          | When                             |
| ----------------- | -------------------------------- |
| `brainstorm.md`   | New feature, component, project  |
| `write-plan.md`   | After design approved            |
| `execute-plan.md` | When plan exists and is approved |
| `tdd.md`          | ANY implementation code          |
| `verify.md`       | Before ANY completion claim      |

### Quality Workflows

| Workflow                  | When                  |
| ------------------------- | --------------------- |
| `request-code-review.md`  | After major feature   |
| `receive-code-review.md`  | When feedback arrives |
| `systematic-debugging.md` | Bug investigation     |

### Advanced Workflows

| Workflow                      | When                             |
| ----------------------------- | -------------------------------- |
| `subagent-driven-dev.md`      | Independent tasks with review    |
| `dispatch-parallel-agents.md` | 2+ independent problems          |
| `git-worktrees.md`            | Need branch isolation (optional) |
| `finish-branch.md`            | Branch work complete (optional)  |
| `writing-skills.md`           | Creating new workflows           |

## Where Things Go

| What                  | Where                             |
| --------------------- | --------------------------------- |
| Task tracking         | `task.md` artifact                |
| Design & plan         | `implementation_plan.md` artifact |
| Verification evidence | `walkthrough.md` artifact         |
| Project state         | `.gemini/current_state.md`        |

## The Anti-Drift Rule

If you find yourself writing code without having checked for a relevant workflow: **STOP.** Read the workflow. Resume correctly.

This isn't optional. It's how you work.
