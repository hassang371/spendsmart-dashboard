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

**Do NOT create `task.md`, `implementation_plan.md`, or `walkthrough.md`.**
These are Gemini's native artifact equivalents — Claude uses the tools above instead.
Each agent uses its own native tracking method. The shared project space is `docs/`.

## Shared Project Docs (cross-agent)

Design docs live in `docs/` and are shared by all agents and humans:

| What | Where |
|---|---|
| Feature LLD | `docs/features/NNN-name.md` |
| Bug reports | `docs/bugs/BUG-NNN-name.md` |
| RFCs / decisions | `docs/rfcs/RFC-NNN-name.md` |
| HLD (living docs) | `docs/design/*.md` |
| Policies | `docs/policies/*.md` |
| Implementation plans | `docs/plans/YYYY-MM-DD-name.md` |
| Session state / notes | auto memory (`MEMORY.md`) — local to Claude only |

**Implementation plans override:** When superpowers or any plugin says to save plans to `docs/superpowers/plans/`, save to `docs/plans/` instead. Do NOT create `docs/superpowers/` — plugin artifacts do not belong in project docs.

**Doc format standard:** See `docs/STANDARDS.md` for required metadata, sections, naming, and status lifecycle.
