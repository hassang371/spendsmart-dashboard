---
description: how to write an implementation plan with bite-sized tasks
---

# Writing Implementation Plans

## Overview

Create comprehensive implementation plans assuming the engineer has zero context. Document everything: which files to touch, complete code, how to test, exact commands. Break into bite-sized tasks using Epic → Story → Task hierarchy. DRY. YAGNI. TDD. Frequent commits.

## Where Plans Are Saved

- **Architecture & approach** → `implementation_plan.md` artifact
- **Task checklist** → `task.md` artifact (using `[ ]` / `[/]` / `[x]` format)

Do NOT create `docs/plans/`, `plan.md`, or any other planning file.

## Hierarchy: Epic → Story → Task

Break work into 3 levels (cherry-picked from scope decomposition pattern):

### Epic (Big Picture)

A major capability or milestone. Example: "User Authentication System"

### Story (User-Facing Unit)

A deliverable piece of value. Example: "User can sign up with email"

### Task (Bite-Sized Action)

A single action (2-5 minutes):

- "Write the failing test" — task
- "Run it to make sure it fails" — task
- "Implement the minimal code to make the test pass" — task
- "Run the tests and make sure they pass" — task
- "Commit" — task

## Plan Structure

### In `implementation_plan.md`:

```markdown
# [Feature Name]

**Goal:** [One sentence]
**Architecture:** [2-3 sentences about approach]
**Tech Stack:** [Key technologies]
**LLD Reference:** [Link to docs/features/NNN-feature.md]

## Architecture Diagram

(Include a Mermaid diagram showing component relationships)

## Proposed Changes

### [Component Name]

- Files to create/modify
- Approach for this component

## Verification Plan

- How to verify changes work
```

### In `task.md` (Epic → Story → Task):

```markdown
# [Epic Name]

## Story 1: [User-facing deliverable]

### Component: [Name]

- [ ] Write failing test for [behavior]
- [ ] Run test, verify it fails
- [ ] Implement minimal code
- [ ] Run test, verify it passes
- [ ] Commit: `feat: add [behavior]`

## Story 2: [Next deliverable]

### Component: [Name]

- [ ] ...
```

## Diagrams in Plans

Include Mermaid diagrams where they add clarity:

| Diagram Type         | When to Use                                     |
| -------------------- | ----------------------------------------------- |
| Dependency graph     | When tasks have ordering constraints            |
| Sequence diagram     | When the plan involves API/service interactions |
| Architecture diagram | When showing component changes                  |

## Task Structure

Each task includes:

- **Files:** exact paths to create/modify/test
- **Steps:** exact code and commands
- **Verification:** exact commands with expected output

## Execution Handoff

After saving the plan, use `notify_user` to present the plan for approval. Once approved, proceed to `execute-plan.md` workflow.

## Remember

- Exact file paths always
- Complete code in plan (not "add validation here")
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits
- Include diagrams where they add clarity
- Reference the LLD doc for design context
