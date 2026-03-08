# Task Tracking + Artifact Mapping

## Task Tracking (Claude-Native)

Use built-in task tools for ALL multi-step work. Create tasks at the START, not the end.

| Tool | When |
|---|---|
| `TaskCreate` | Start of any multi-step work — create all tasks upfront |
| `TaskUpdate status:in_progress` | When you begin a task |
| `TaskUpdate status:completed` | When a task is fully done (not just "should be done") |
| `TaskList` | Check for in-progress tasks from prior sessions at startup |
| `TaskGet` | Get details on a specific task |

**Never create `task.md` files.** Tasks live in Claude Code's task system only.

## Artifact Mapping

| What | Where |
|---|---|
| Feature LLD | `docs/features/NNN-name.md` |
| Bug reports | `docs/bugs/BUG-NNN-name.md` |
| RFCs / big decisions | `docs/rfcs/RFC-NNN-name.md` |
| HLD (living docs) | `docs/design/*.md` |
| Session state / notes | auto memory (`MEMORY.md`) |

**NEVER create:**
- `task.md`
- `implementation_plan.md`
- `walkthrough.md`
- `plan.md`
- `docs/plans/` directory
