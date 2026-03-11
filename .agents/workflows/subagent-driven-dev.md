---
description: how to execute plans using subagents with two-stage code review
---

# Subagent-Driven Development

## When to Use

Use when executing implementation plans where tasks are independent and can be parallelized via subagents.

## Process

1. **Load the FULL subagent-driven-dev skill folder** (Skill Loading Protocol):
   - `list_dir` on `.agents/skills/subagent-driven-dev/`
   - `view_file` on `SKILL.md` AND every file in `references/`, `agents/`, `scripts/`
2. Follow the two-stage review process (spec compliance → code quality)
3. Track progress in `task.md` artifact
