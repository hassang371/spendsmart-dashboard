# Superpowers Workflow Rules

## Discovery Gate (fires during investigation, BEFORE brainstorming)

When performing any research, investigation, or code analysis:

**If you find a defect, dead code, broken pipeline, or missing data:**
1. **STOP immediately** — do not continue the analysis, do not discuss solutions
2. Create `docs/bugs/BUG-NNN-name.md` via the design-docs skill
3. Run spec review on the bug report (`superpowers:code-reviewer`)
4. Commit: `git commit -m "docs: add BUG-NNN — <name>"`
5. Only THEN return to investigation or proceed to brainstorm the fix

This gate fires REGARDLESS of whether code is about to be written. Investigation that finds a
defect ALWAYS produces a committed bug report. The user must not have to ask for this.

**Investigation output contract:** Every research task concludes with:
- For each confirmed defect → `BUG-NNN` doc committed
- For each unconfirmed observation → scratch note in `docs/investigations/` (not a formal doc)
- For each missing feature noticed → note only; create Feature LLD only if user confirms

---

## Brainstorming Gate

Before any feature, bug fix, architectural decision, or ambiguous request:
→ Invoke `superpowers:brainstorming` via Skill tool.

**Skip brainstorming ONLY if the change is trivially scoped.**

Trivially scoped means ONE of these EXACTLY:
- Fixing a misspelled word or string literal (no logic change)
- Renaming a variable or function (no behavior change, single file)
- Changing a log message wording
- Updating a comment or docstring

It does NOT mean:
- Anything touching logic, data flow, or API shape
- Changes spanning more than one file
- Configuration changes with behavioral impact
- Any database schema or migration change
- "I know what to do" — knowing the solution doesn't skip the documentation

**When in doubt → brainstorm.** If you're asking whether it counts as trivial, it doesn't.

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
| GitOps / ArgoCD / Flux | Skill tool | `gitops-workflows:gitops-workflows` |
| IaC / Terraform | Skill tool | `iac-terraform:iac-terraform` |
| Kubernetes troubleshooting | Skill tool | `k8s-troubleshooter:k8s-troubleshooter` |
| AWS cost optimization | Skill tool | `aws-cost-optimization:aws-cost-optimization` |

## Skill Loading Protocol

**Two tiers:**
1. **Plugin skills** (superpowers:*, fullstack-dev-skills:*, etc.) → use `Skill` tool
2. **Local `.claude/skills/`** → Read `SKILL.md`, then load references **on demand** as SKILL.md instructs

**Progressive disclosure rule:** Do NOT preload all references. SKILL.md is the router — it tells you which file to read and when. Loading everything upfront wastes context.

## Anti-Drift Protocol

Check these at the three moments that matter:

**During investigation:**
- Did I find a defect? → Discovery Gate fired? → Bug report committed before discussing solution?

**Before writing any code:**
- Have I brainstormed? Have I read docs-driven-dev? Is there a committed design doc?
- Have I run spec review on that doc? Did it pass?
- Have I written a failing test first?

**Before claiming done:**
- Have I re-read the LLD and recorded any deviations (Step 4.5)?
- Have I run `superpowers:verification-before-completion` and read the actual output?
- Does my commit have a `Refs:` line pointing to the design doc?

**Always:**
- Am I preloading ALL skill references without SKILL.md directing me? If yes, stop.

**Red flags — you are drifting if:**
- Found a defect but wrote prose about it instead of creating a bug report
- Wrote code without a failing test
- Said "should work" without running a command
- Created `task.md`, `implementation_plan.md`, or `walkthrough.md`
- Claimed done without verification output
- Committed `fix:` or `feat:` without a `Refs:` line
- Loaded all skill references without SKILL.md telling you to
- Transitioned from investigation to solution discussion without a committed doc
