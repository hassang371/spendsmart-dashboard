---
description: how to brainstorm a design before implementation
---

# Brainstorming Ideas Into Designs

## Overview

Help turn ideas into fully-formed designs through collaborative dialogue. Understand the project context, ask questions to refine the idea, then present the design for approval.

**HARD GATE:** Do NOT write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies to EVERY project regardless of perceived simplicity.

## Anti-Pattern: "This Is Too Simple To Need A Design"

Every project goes through this process. A todo list, a single-function utility, a config change — all of them. "Simple" projects are where unexamined assumptions cause the most wasted work.

## Process

### 1. Explore Project Context

- Check existing files, docs, dependencies
- Read `.gemini/tech-stack.md` if it exists
- Understand current project state

### 2. Ask Clarifying Questions

- One question at a time — don't overwhelm
- Prefer multiple choice when possible
- Focus: purpose, constraints, success criteria
- Use `notify_user` to ask questions

### 3. Propose 2-3 Approaches

- Present options with trade-offs
- Lead with your recommended option and explain why
- YAGNI ruthlessly — remove unnecessary features

### 4. Present Design

- Scale each section to its complexity
- Ask after each section whether it looks right
- Cover: architecture, components, data flow, error handling, testing
- Use `notify_user` for section-by-section approval

### 5. Write Design Doc

- Save the validated design to `implementation_plan.md` artifact
- Include: Goal, Architecture, Proposed Changes, Verification Plan

### 6. Transition to Implementation

- After design is approved, invoke the `write-plan.md` workflow
- Do NOT invoke any other workflow. `write-plan.md` is the next step.

## Key Principles

- **One question at a time** — Don't overwhelm with multiple questions
- **Multiple choice preferred** — Easier to answer than open-ended
- **YAGNI ruthlessly** — Remove unnecessary features from all designs
- **Explore alternatives** — Always propose 2-3 approaches before settling
- **Incremental validation** — Present design, get approval before moving on
