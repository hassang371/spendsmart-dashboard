# Skills Registry — situation → skill mapping

> **Purpose:** Single source of truth for which skill handles which situation. The workflow
> file (`.claude/workflow.md`) and rules use SITUATION LANGUAGE only — no skill names. When a
> plugin changes or a skill is added/removed, only this file needs updating.

**Last updated:** 2026-05-05
**Active plugins (6):** caveman, codex, impeccable, mattpocock-skills, skill-creator, superpowers

---

## Always-on situational bindings

| Situation | Skill | Plugin | Notes |
|---|---|---|---|
| Discovery / investigation defect-found | (no skill — Discovery Gate rule fires) | — | See `documentation-gate.md` Gate 1 |
| Pre-design interview / brainstorm (project-aware) | `mattpocock-skills:grill-with-docs` | mattpocock | Reads CONTEXT.md + ADRs |
| Pre-design interview (no project context yet) | `mattpocock-skills:grill-me` | mattpocock | Fallback when no docs to ground in |
| Design doc creation (LLD / Bug / ADR) | `orchestra:design-docs` | orchestra (user-scoped plugin) | Replaces former project-scoped `design-docs` skill (deleted 2026-05-06). Auto-detects `.claude/orchestra.json`. |
| Spec review on docs | `superpowers:requesting-code-review` | superpowers | Structured doc critique |
| Plan writing (multi-step) | `superpowers:writing-plans` | superpowers | **Override save path:** `docs/plans/YYYY-MM-DD-name.md` (NOT `docs/superpowers/specs/`) |
| Plan execution (subagents) | `superpowers:executing-plans` or `superpowers:subagent-driven-development` | superpowers | |
| TDD execution (vertical slicing) | `mattpocock-skills:tdd` | mattpocock | Vertical-slice red-green-refactor |
| TDD principle (iron law: no code without failing test) | `superpowers:test-driven-development` (rule-only) | superpowers | Treat as principle. Execute via mattpocock-skills:tdd. |
| Bug debugging loop | `mattpocock-skills:diagnose` | mattpocock | Reproduce→minimize→hypothesize→instrument→fix→regression-test |
| Self code review (pre-commit) | `caveman:caveman-review` | caveman | Terse, line-by-line |
| Adversarial review (optional second opinion) | `codex:adversarial-review` (slash cmd) | codex | Different model = different blind spots |
| Adversarial / stuck-investigation rescue | `codex:rescue` (subagent) | codex | When investigation hits wall |
| Verification before complete | `superpowers:verification-before-completion` | superpowers | **Bug override:** also requires explicit user confirmation |
| Architecture refactor / deepening | `mattpocock-skills:improve-codebase-architecture` | mattpocock | Reads CONTEXT.md + ADRs |
| Issue triage | `mattpocock-skills:triage` | mattpocock | Five-role state machine |
| Plan → issues breakdown | `mattpocock-skills:to-issues` | mattpocock | Tracer-bullet vertical slices |
| Skill creation / iteration / eval | `skill-creator:skill-creator` | skill-creator | Eval framework + variance analysis |
| Frontend design / UI critique | `impeccable:impeccable` | impeccable | Next.js + Tailwind aware |
| Compression / brief mode | `caveman:caveman` | caveman | Auto-active via SessionStart hook |
| Higher-level codebase view | (mattpocock zoom-out — currently dormant) | mattpocock | Re-enable in plugin.json if needed |
| Commit messages | `caveman:caveman-commit` | caveman | Conventional commits, terse, auto-trigger on staging |
| Branch finishing / PR creation | `superpowers:finishing-a-development-branch` | superpowers | |
| Receiving code review (verifying feedback) | `superpowers:receiving-code-review` | superpowers | |
| Parallel independent tasks | `superpowers:dispatching-parallel-agents` | superpowers | |
| Worktree isolation | `superpowers:using-git-worktrees` | superpowers | |
| Compress memory file | `caveman:compress` | caveman | Compress CLAUDE.md / MEMORY.md to caveman format |
| PR / diff review (anthropic native) | `review` | anthropic builtin | Alternative to caveman:caveman-review for full PRs |
| Security review | `security-review` | anthropic builtin | Dedicated security lens |

---

## Skills available but NOT bound to situations (use ad-hoc)

These are fine to invoke when explicitly needed, but the workflow does not auto-route to them:

- `superpowers:brainstorming` — superseded by `mattpocock:grill-with-docs` (which reads project docs). Use the superpowers version only if context-free brainstorm is wanted.
- `superpowers:writing-skills` — superseded by `skill-creator` (has eval framework).
- `mattpocock-skills:write-a-skill` — superseded by `skill-creator`.
- `mattpocock-skills:to-prd` — uses PRD vocabulary. SCALE uses Feature LLD instead.
- `mattpocock-skills:caveman` — duplicate of `caveman:caveman` (real plugin with hooks). Use the real one.
- `init` (anthropic) — for new repos, not SCALE.

---

## Disabled but installed (none currently)

All previously-installed-but-disabled plugins were uninstalled during the 2026-05-05 cleanup.
Future plugins disabled-but-known would be listed here.

---

## Override rules (rules engine should respect these)

| # | Override | Source skill | Override |
|---|---|---|---|
| A | Save plan path | superpowers:writing-plans | `docs/plans/YYYY-MM-DD-name.md` (not `docs/superpowers/specs/`) |
| B | Save design path | superpowers:brainstorming | `docs/features/`, `docs/bugs/`, `docs/adr/` per type (not `docs/superpowers/specs/`) |
| D | Doc taxonomy | mattpocock-skills:to-prd | Don't use. Use `orchestra:design-docs` skill for LLDs instead. |
| E | TDD execution shape | superpowers:test-driven-development | Iron-law principle preserved as rule. Execute via mattpocock-skills:tdd vertical slicing. |
| F | Caveman duplicate | mattpocock-skills:caveman | Use `caveman:caveman` (real plugin). Mattpocock copy is suppressed. |

(C — `docs/adr/` ADR override — no longer needed because SCALE adopted ADR taxonomy
to align with mattpocock skills.)

---

## Lookup procedure for Claude

When a workflow rule says "spec review the doc" or "execute via TDD":

1. Find the matching situation in the table above
2. Use the bound skill
3. If skill not found in current session's available-skills list:
   a. Check if plugin is enabled (settings + `/reload-plugins`)
   b. If still missing → tell user, do NOT silently skip
4. Apply any override rules (paths, formats)

The workflow file never names skills directly. This file is the only place where situation
↔ skill bindings live.

---

## Adding a new skill / plugin

When a new plugin is installed:
1. Run `/reload-plugins`
2. Read each skill's description
3. For each skill, decide:
   a. Does it cover a situation NOT in the table → add a new row
   b. Does it overlap an existing situation → decide winner, update table, mark loser
4. Note any path / format conflicts → add to override rules
5. Update `MEMORY.md` with the decision rationale (so future sessions can recover context)

## Removing a skill / plugin

When a plugin is removed:
1. Find rows in the table bound to its skills
2. Re-bind to next-best alternative OR mark as "no candidate"
3. Update workflow rules if a no-candidate situation is critical
