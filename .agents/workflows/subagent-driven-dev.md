---
description: how to execute plans using subagents with two-stage code review
---

# Subagent-Driven Development

## When to Use

Use when executing implementation plans where tasks are independent and can be parallelized via subagents.

## Process

1. **Read** `.agents/skills/subagent-driven-dev/SKILL.md` for the full subagent orchestration framework
2. Follow its two-stage review process:
   - Stage 1: Spec compliance review (does it match the plan?)
   - Stage 2: Code quality review (is it production-ready?)
3. Use bundled agent prompts in `.agents/skills/subagent-driven-dev/agents/`:
   - `implementer-prompt.md` — Prompt template for implementation subagents
   - `spec-reviewer-prompt.md` — Prompt template for spec compliance review
   - `code-quality-reviewer-prompt.md` — Prompt template for code quality review
4. Track progress in `task.md` artifact
