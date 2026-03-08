# Superpowers Workflow Rules

## Brainstorming Gate

Before any feature, bug fix, architectural decision, or ambiguous request:
→ Invoke `superpowers:brainstorming` via Skill tool.

**Skip brainstorming ONLY if:**
- The request is a pure question with no code change implied, OR
- The task is trivially scoped (rename a variable, fix a typo)

**When in doubt → brainstorm.**

Brainstorming IS Step 1 of docs-driven-dev. They are the same thing — not two separate steps.

## Master Workflow

For ANY code change: Read `.claude/workflows/docs-driven-dev.md` and follow it.

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

## Anti-Drift Protocol (check every 3 turns)

1. Have I loaded docs-driven-dev for this code change? If not, read it now.
2. Have I brainstormed before writing code? If not, stop and invoke `superpowers:brainstorming`.
3. Have I written the test first? If not, delete the code and write the test.
4. Am I about to claim completion? STOP — run `superpowers:verification-before-completion` first.
5. Am I preloading ALL skill references without SKILL.md directing me? If yes, stop.

**Red flags — you are drifting if:**
- Wrote code without a failing test
- Said "should work" without running a command
- Created `task.md`, `implementation_plan.md`, or `walkthrough.md`
- Claimed done without verification output
- Loaded all skill references without SKILL.md telling you to
