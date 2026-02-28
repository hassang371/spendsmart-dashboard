---
description: how to write an implementation plan with bite-sized tasks
---

# Writing Implementation Plans

## Overview

Create comprehensive implementation plans assuming the engineer has zero context. Document everything: which files to touch, complete code, how to test, exact commands. Break into bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

## Where Plans Are Saved

- **Architecture & approach** → `implementation_plan.md` artifact
- **Task checklist** → `task.md` artifact (using `[ ]` / `[/]` / `[x]` format)

Do NOT create `docs/plans/`, `plan.md`, or any other planning file.

## Bite-Sized Task Granularity

Each step is one action (2-5 minutes):

- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

## Plan Structure

### In `implementation_plan.md`:

```markdown
# [Feature Name]

**Goal:** [One sentence]
**Architecture:** [2-3 sentences about approach]
**Tech Stack:** [Key technologies]

## Proposed Changes

### [Component Name]

- Files to create/modify
- Approach for this component

## Verification Plan

- How to verify changes work
```

### In `task.md`:

```markdown
# [Feature Name] Tasks

## Component 1: [Name]

- [ ] Write failing test for [behavior]
- [ ] Run test, verify it fails
- [ ] Implement minimal code
- [ ] Run test, verify it passes
- [ ] Commit

## Component 2: [Name]

- [ ] ...
```

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
