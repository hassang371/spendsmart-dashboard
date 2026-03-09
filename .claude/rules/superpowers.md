# Superpowers Workflow Rules

## Brainstorming Gate

Before any feature, bug fix, architectural decision, or ambiguous request:
→ Invoke `superpowers:brainstorming` via Skill tool.

**Skip brainstorming ONLY if:**
- The request is a pure question with no code change implied, OR
- The change is trivially scoped: you know exactly what to change, it's a single file/function, and the approach is obvious (rename a variable, fix a typo, update a string)

**When in doubt → brainstorm.** Small bug fixes that aren't obviously scoped still need brainstorming.

Brainstorming IS Step 1 of docs-driven-dev. They are the same thing — not two separate steps.

## Skill Table

| Situation | How | Target |
|---|---|---|
| Any code change (master) | Read file | `.claude/workflows/docs-driven-dev.md` |
| Brainstorming | Skill tool | `superpowers:brainstorming` |
| Design docs (LLD/HLD/RFC) | Read files | `.claude/skills/design-docs/SKILL.md` (progressive) |
| Implementation plans | Skill tool | `superpowers:writing-plans` |
| TDD execution | Skill tool | `superpowers:test-driven-development` |
| Execute plan (subagent) | Skill tool | `superpowers:executing-plans` |
| Subagent iteration | Skill tool | `superpowers:subagent-driven-development` |
| Debugging | Skill tool | `superpowers:systematic-debugging` |
| Parallel tasks | Skill tool | `superpowers:dispatching-parallel-agents` |
| Verification / done claim | Skill tool | `superpowers:verification-before-completion` |
| Code review | Skill tool | `superpowers:requesting-code-review` |
| Receiving review | Skill tool | `superpowers:receiving-code-review` |
| Branch isolation | Skill tool | `superpowers:using-git-worktrees` |
| Branch completion | Skill tool | `superpowers:finishing-a-development-branch` |
| Creating/editing skills | Skill tool | `superpowers:writing-skills` |
| Next.js / React | Skill tool | `fullstack-dev-skills:nextjs-developer` |
| Python / FastAPI | Skill tool | `fullstack-dev-skills:fastapi-expert` |
| Database / Postgres | Skill tool | `fullstack-dev-skills:postgres-pro` |
| TypeScript | Skill tool | `fullstack-dev-skills:typescript-pro` |
| Full-stack feature | Skill tool | `fullstack-dev-skills:fullstack-guardian` |
| Security review | Skill tool | `fullstack-dev-skills:secure-code-guardian` |
| CI/CD | Skill tool | `ci-cd:ci-cd` |
| Monitoring / SLOs | Skill tool | `monitoring-observability:monitoring-observability` |

## Skill Loading Protocol

**Two tiers:**
1. **Plugin skills** (superpowers:*, fullstack-dev-skills:*, etc.) → use `Skill` tool
2. **Local `.claude/skills/`** → Read `SKILL.md`, then load references **on demand** as SKILL.md instructs

**Progressive disclosure rule:** Do NOT preload all references. SKILL.md is the router — it tells you which file to read and when. Loading everything upfront wastes context.

## Anti-Drift Protocol

Check these at the two moments that matter — **before writing any code** and **before claiming done**:

- Before writing code: Have I brainstormed? Have I read docs-driven-dev? Have I written a failing test first?
- Before claiming done: Have I run `superpowers:verification-before-completion` and read the actual output?
- Always: Am I preloading ALL skill references without SKILL.md directing me? If yes, stop.

**Red flags — you are drifting if:**
- Wrote code without a failing test
- Said "should work" without running a command
- Created `task.md`, `implementation_plan.md`, or `walkthrough.md`
- Claimed done without verification output
- Loaded all skill references without SKILL.md telling you to
