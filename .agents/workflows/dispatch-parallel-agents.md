---
description: how to dispatch parallel agents for independent tasks
---

# Dispatching Parallel Agents

## Overview

When facing 2+ independent problems, dispatch one agent per problem domain. Let them work concurrently.

**Core principle:** Dispatch one agent per independent problem. Let them work in parallel.

## When to Use

**Use when:**

- 3+ test files failing with different root causes
- Multiple subsystems broken independently
- Each problem can be understood without context from others
- No shared state between investigations

**Don't use when:**

- Failures are related (fix one might fix others)
- Need full system state understanding
- Agents would interfere (editing same files)

## The Pattern

### 1. Identify Independent Domains

Group failures by what's broken. Each domain must be independent.

### 2. Create Focused Agent Tasks

Each agent gets:

- **Specific scope:** one subsystem/file
- **Clear goal:** make these tests pass / fix this bug
- **Constraints:** don't change code outside scope
- **Expected output:** summary of findings and changes

### 3. Dispatch in Parallel

Use subagent tools to dispatch concurrently.

### 4. Review and Integrate

When agents return:

- Read each summary
- Verify fixes don't conflict
- Run full test suite
- Integrate all changes

## Common Mistakes

| Mistake                  | Fix                                        |
| ------------------------ | ------------------------------------------ |
| Too broad scope          | One file/subsystem per agent               |
| No context in prompt     | Paste error messages and test names        |
| No constraints           | Specify what NOT to change                 |
| Vague output expectation | "Return summary of root cause and changes" |

## Key Benefits

1. **Parallelization** — multiple investigations happen simultaneously
2. **Focus** — each agent has narrow scope
3. **Independence** — agents don't interfere
4. **Speed** — N problems solved in time of 1
