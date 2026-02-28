# Skills + Workflows Guide

## Architecture

```
.agents/
├── workflows/     ← Lightweight .md files (organic triggers via Global Rule)
└── skills/        ← Heavy folders with scripts, references, templates
```

**Workflow** = Single `.md` file. Pure procedure, no bundled assets.
**Skill** = Folder with `SKILL.md` + scripts/, references/, assets/.
**Skill+Workflow pair** = Heavy skill folder + thin routing workflow for organic trigger.

## When to Load What

1. **Workflows** — Read the `.md` file directly when the Activation Map triggers it
2. **Skills** — Read `SKILL.md` first, then load references on-demand via the reference table
3. **Skill+Workflow pairs** — Workflow routes you to the skill folder; read SKILL.md there

## Complete Inventory (32 Skills, 19 Workflows)

### Process Skills (how you work)

| Skill                  | Paired Workflow?          | Trigger                                     |
| ---------------------- | ------------------------- | ------------------------------------------- |
| `skill-creator`        | `writing-skills.md`       | Creating new skills or workflows            |
| `systematic-debugging` | `systematic-debugging.md` | Any bug, test failure, unexpected behavior  |
| `tdd`                  | `tdd.md`                  | Writing any production code                 |
| `request-code-review`  | `request-code-review.md`  | After major feature, before merge           |
| `subagent-driven-dev`  | `subagent-driven-dev.md`  | Executing plans with independent tasks      |
| `mcp-builder`          | —                         | Building MCP servers (explicit)             |
| `webapp-testing`       | —                         | Testing web apps with Playwright (explicit) |

### Context Engineering (how you manage context)

| Skill                  | Trigger                                                          |
| ---------------------- | ---------------------------------------------------------------- |
| `context-fundamentals` | Understanding context windows, attention, progressive disclosure |
| `context-degradation`  | Diagnosing context failures, lost-in-middle issues               |
| `context-compression`  | Summarizing context, reducing token usage                        |
| `context-optimization` | KV-cache optimization, context partitioning                      |
| `evaluation`           | Building test frameworks, measuring agent quality                |

### Domain Skills — System Design & Architecture

| Skill                     | Trigger                                                   |
| ------------------------- | --------------------------------------------------------- |
| `architecture-designer`   | System design, ADRs, architecture patterns, scalability   |
| `api-designer`            | REST API design, OpenAPI, versioning, pagination          |
| `microservices-architect` | Service decomposition, DDD, saga patterns, event sourcing |
| `fullstack-guardian`      | Implementing features across frontend + backend           |
| `feature-forge`           | Requirements gathering, feature definition, specs         |

### Domain Skills — Frontend & Languages

| Skill              | Trigger                                               |
| ------------------ | ----------------------------------------------------- |
| `react-expert`     | React 18+, hooks, state management, Server Components |
| `nextjs-developer` | Next.js App Router, Server Actions, data fetching     |
| `typescript-pro`   | Advanced types, generics, type guards, monorepo       |
| `python-pro`       | Type hints, async, pytest, performance                |

### Domain Skills — Security & Testing

| Skill                  | Trigger                                               |
| ---------------------- | ----------------------------------------------------- |
| `secure-code-guardian` | Auth, input validation, OWASP Top 10, encryption      |
| `test-master`          | Unit, integration, E2E, performance, security testing |

### Domain Skills — Database

| Skill                | Trigger                                       |
| -------------------- | --------------------------------------------- |
| `database-optimizer` | Query optimization, indexing, execution plans |

### DevOps & Infrastructure

| Skill                | Paired Workflow?        | Trigger                                           |
| -------------------- | ----------------------- | ------------------------------------------------- |
| `devops-engineer`    | —                       | CI/CD, Docker, K8s, deployment strategies (broad) |
| `monitoring-expert`  | `monitoring-expert.md`  | Prometheus, Grafana, OTel, SLOs, alerting         |
| `ci-cd`              | `ci-cd.md`              | Pipeline design, GH Actions/GitLab CI templates   |
| `k8s-troubleshooter` | `k8s-troubleshooter.md` | Pod failures, cluster health, incident response   |
| `sre-engineer`       | —                       | SLIs/SLOs, error budgets, incident management     |
| `gitops-workflows`   | —                       | ArgoCD, Flux, progressive delivery (explicit)     |
| `iac-terraform`      | —                       | Terraform modules, state management (explicit)    |
| `aws-cost-optimizer` | —                       | AWS cost analysis, RI recommendations (explicit)  |

### Standalone Workflows (no skill folder)

| Workflow                      | Trigger                                             |
| ----------------------------- | --------------------------------------------------- |
| `brainstorm.md`               | Any creative work, feature request                  |
| `write-plan.md`               | After brainstorming approved                        |
| `execute-plan.md`             | After plan approved                                 |
| `verify.md`                   | Before any completion claim                         |
| `receive-code-review.md`      | When code review feedback arrives                   |
| `dispatch-parallel-agents.md` | 2+ unrelated tasks                                  |
| `git-worktrees.md`            | When git isolation needed                           |
| `finish-branch.md`            | When ready to merge/PR                              |
| `context-checkpoint.md`       | Long sessions (5+ turns)                            |
| `global-rule.md`              | Framework anchor (pasted into Antigravity Rules UI) |

## How Skills Get Discovered

1. **Antigravity auto-discovery** — Skills in `.agents/skills/` with `SKILL.md` appear in the system prompt's `<skills>` section with their description
2. **Workflow auto-discovery** — Workflows in `.agents/workflows/` appear in the `<workflows>` section
3. **Global Rule Activation Map** — Core process workflows are explicitly mapped for guaranteed activation
4. **Progressive disclosure** — SKILL.md loads first (~80 lines), references load on-demand via reference tables
