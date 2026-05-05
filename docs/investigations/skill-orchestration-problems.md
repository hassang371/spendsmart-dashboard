# Investigation: Skill Orchestration Problems

> **Type:** Investigation (scratch note — not a formal doc)
> **Date:** 2026-05-05
> **Status:** Open — needs dedicated session
> **Raised by:** Hassan (session handoff)

---

## Context

SCALE uses Claude Code with two skill/plugin sources:

- **Project-scoped:** `.claude/skills/` — custom skills created by Hassan (design-docs, etc.)
- **Global plugins:** `~/.claude/skills/` and `~/.claude/plugins/` — third-party plugins (matt pocock skills, superpowers, caveman, etc.)

A session on 2026-05-05 revealed a cluster of problems with how skills are discovered, selected, and executed. This document records those problems in detail for a dedicated follow-up session.

---

## Problem 1: Rules Hardcode Skill Names Instead of Situations

`.claude/rules/superpowers.md` and `.claude/CLAUDE.md` reference skills by their exact plugin path:

```
superpowers:test-driven-development
superpowers:brainstorming
superpowers:code-reviewer
superpowers:verification-before-completion
```

These are names as they appear in the `superpowers` plugin's internal routing, but they do not always match what is actually registered in the available skills list. In the 2026-05-05 session:

- `superpowers:test-driven-development` was referenced in `docs-driven-dev.md` as the skill to invoke for TDD
- The actual registered skill for TDD was `tdd` (from the matt pocock skills plugin)
- Claude looked for the exact name `superpowers:test-driven-development`, did not find it, and **silently skipped TDD entirely** — executing TDD manually without invoking the skill

This is a silent failure mode: no error, no warning, just the skill being bypassed. The hardcoded name in the rule became a dead reference.

The same happened with `superpowers:code-reviewer` — referenced in design-docs SKILL.md for spec review, not available in this session, so spec review was done manually without invoking the correct skill.

---

## Problem 2: No Skill Discovery Fallback

When a skill reference fails (name not found), Claude has no fallback procedure. The current behaviour is:

1. Try exact name → fail
2. Execute the intent manually (if Claude decides to) or skip entirely

There is no step that says: "name not found → search available skills list semantically → find closest match → use it." The available skills list is visible in the session context (shown by `/context`), but Claude does not cross-reference it when a named skill lookup fails.

In the 2026-05-05 session, the `tdd` skill was listed in the available skills and would have been found by any semantic search for "test-driven development." It was never checked.

---

## Problem 3: Duplicate Skills Across Plugins With No Precedence Rule

Both the matt pocock plugin and the superpowers plugin provide skills that cover overlapping ground:

| Situation | Matt Pocock Skill | Superpowers Skill |
|---|---|---|
| TDD / test-first | `tdd` | `superpowers:test-driven-development` |
| Creating docs | `to-prd`, `to-issues` | `superpowers:brainstorming` + design-docs |
| Code review | `caveman:caveman-review` | `superpowers:code-reviewer` |
| Architecture | `improve-codebase-architecture` | (none direct) |

No rule exists for:
- Which skill to use when both options exist
- Whether to read both skills before deciding
- Whether they conflict in approach (they do — see Problem 5)
- Which plugin's workflow takes precedence in a given session

In the 2026-05-05 session, the matt pocock `tdd` skill was available but not used. Instead, the TDD steps from `docs-driven-dev.md` (superpowers workflow) were followed, which led to the horizontal-slice anti-pattern that the matt pocock `tdd` skill explicitly warns against.

---

## Problem 4: Skill Location Is Fragmented With No Unified Index

Skills exist in at least three locations:

1. **`.claude/skills/`** — project-scoped custom skills (design-docs, etc.)
2. **`~/.claude/skills/`** — global user skills from matt pocock plugin (tdd, grill-me, improve-codebase-architecture, etc.)
3. **`~/.claude/plugins/`** — namespaced plugin skills (caveman:*, superpowers:*, fullstack-dev-skills:*, etc.)

There is no index that maps situations to skills across all three locations. Claude must infer what exists from the available skills list in the session context, which is long and not organized by situation or purpose.

When Claude needs a skill, it currently:
- Reads the rule that names the skill
- Tries to invoke it directly
- Does not scan the full available skills list to find alternatives

This means skills installed later (or in a different location than expected) are invisible unless explicitly referenced by name in a rule.

---

## Problem 5: Conflicting Workflow Definitions Across Plugins

Two workflow documents are active simultaneously:

**Superpowers workflow** (`.claude/rules/superpowers.md`, `.claude/workflows/docs-driven-dev.md`):

```
Brainstorm → Document → Plan → Execute → Verify → Commit
```

- Execute phase invokes `superpowers:test-driven-development`
- Write all tests for a feature, implement, verify
- Emphasizes design docs before any code

**Matt Pocock TDD skill** (`~/.claude/skills/tdd/SKILL.md`):

```
Plan → Tracer Bullet → Incremental RED→GREEN loops → Refactor
```

- Explicitly prohibits writing all tests before implementation ("horizontal slicing = anti-pattern")
- One test → one implementation → repeat
- No mention of design docs

These two workflows directly contradict each other on TDD execution style. When both are active in a session, there is no rule for which takes precedence. In the 2026-05-05 session, the superpowers workflow was followed (all tests written first, then all implementation), which is exactly the anti-pattern the matt pocock TDD skill warns against.

---

## Problem 6: Doc Type Vocabulary Conflict Between Systems

Hassan's project uses a specific doc taxonomy:

| Doc Type | Location | Purpose |
|---|---|---|
| Feature LLD | `docs/features/NNN-*.md` | Low-level design for a feature |
| Bug Report | `docs/bugs/BUG-NNN-*.md` | Bug investigation + fix design |
| RFC (full/short) | `docs/rfcs/RFC-NNN-*.md` | Architectural decisions |
| HLD | `docs/design/*.md` | Living system architecture docs |
| Implementation Plan | `docs/plans/` | Step-by-step execution plan |

Matt pocock's plugin skills use a different vocabulary:

| Matt Pocock Term | Used By | Meaning |
|---|---|---|
| PRD | `to-prd` skill | Product requirements doc |
| ADR | `docs/agents/domain.md` | Architectural decision record |
| Issue | `to-issues`, `triage` skills | GitHub issue |
| Ticket | `triage` skill | Any issue tracker item |

When matt pocock skills run (e.g., `to-prd`, `to-issues`, `improve-codebase-architecture`), they reference their vocabulary. When SCALE's design-docs skill runs, it references SCALE's vocabulary. There is no mapping between them.

Concrete example: `docs/agents/domain.md` (set up in this session) instructs skills to read `docs/adr/` for architectural decisions. But `docs/STANDARDS.md` explicitly states `docs/adr/` is deprecated — all decisions go in `docs/rfcs/`. The `docs/adr/` directory was created in this session by the matt pocock setup skill, contradicting the project standard. This conflict was not caught because no mapping exists.

---

## Problem 7: Progressive Disclosure Is Not Enforced

Hassan's intent: skills should be discovered situationally based on what is happening, not pre-loaded or hardcoded. If he installs a new skill, it should become discoverable without editing any rule files.

Current state: discovery is entirely hardcoded. A new skill installed to `~/.claude/skills/` is invisible until a rule explicitly references it by name. There is no mechanism for:
- Claude to scan available skills and identify relevant ones for the current situation
- New skills to register themselves into the routing logic
- Skills to declare what situations they handle (beyond their description text)

---

## Problem 8: SCALE's Design-Docs Skill Needs Improvement and Interop

The `design-docs` skill (`.claude/skills/design-docs/SKILL.md`) was built before the matt pocock plugins were installed. Issues:

- It does not know about the doc vocabulary used by matt pocock skills
- It references `superpowers:code-reviewer` for spec review, which is unavailable
- Its `docs/STANDARDS.md` reference deprecates `docs/adr/` but the matt pocock domain setup creates `docs/adr/` — the skill does not handle this conflict
- The skill has never been tested or improved using the `skill-creator` skill available in `~/.claude/skills/`

No iterative improvement process has been run on this skill. It was written once and used as-is.

---

## Problem 9: Plugin Coherence — Partial Plugin Usage

When a plugin is installed (e.g., matt pocock), it provides a coherent set of skills designed to work together. In the 2026-05-05 session, matt pocock skills were used partially:

- `improve-codebase-architecture` — used ✓
- `tdd` — skipped ✗
- `grill-me` / `grill-with-docs` — not used ✗
- `caveman:caveman-review` — not used for code review ✗

No rule enforces "when using a plugin, prefer completing the workflow using that plugin's skills." The session mixed superpowers workflow with matt pocock exploration skills, getting the worst of both.

---

## Summary of Problem Dimensions

| # | Problem | Impact |
|---|---|---|
| 1 | Rules hardcode skill names | Skills silently skipped when name drifts |
| 2 | No discovery fallback | Available skills go unused |
| 3 | Duplicate skills, no precedence | Wrong skill chosen by accident |
| 4 | Fragmented skill locations | Skills invisible without explicit references |
| 5 | Conflicting workflow definitions | Anti-patterns followed undetected |
| 6 | Doc vocabulary conflict | Cross-plugin doc references break or contradict project standards |
| 7 | No progressive disclosure | New skills stay invisible |
| 8 | Design-docs skill not maintained | Interop gaps accumulate |
| 9 | Partial plugin usage | Plugin's coherent workflow broken up |

---

## What the Dedicated Session Should Focus On

This investigation does NOT contain proposed solutions — that is for the dedicated session.

The session should:
1. Read this document in full
2. Read `superpowers.md`, `docs-driven-dev.md`, `CLAUDE.md` (project + global)
3. Read the matt pocock TDD, grill-me, improve-codebase-architecture, to-prd, to-issues skills
4. Read the `skill-creator` skill before proposing any changes to design-docs
5. Propose and discuss solutions to all 9 problems above
6. Implement agreed solutions (likely: new routing files, skill updates, CLAUDE.md changes)

---

*Handoff created: 2026-05-05. Do not resolve this investigation until all 9 problems have a documented solution and implementation plan.*
