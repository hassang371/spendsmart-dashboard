# Phase 5 — design-docs Skill Iteration + Public Plugin Extraction

> **Date:** 2026-05-06
> **Status:** In Progress
> **DRI:** Hassan
> **LLD:** N/A (skill iteration, not feature work)

## Goal

Iterate `.claude/skills/design-docs/` to industry-best-in-class state, then extract as a public Claude Code plugin (`design-docs-claude`).

Track 1 = SCALE-internal iteration. Track 2 = public plugin extraction (deferred).

## Track 1 Scope

1. Fix template defects per STANDARDS.md audit (bug-report, feature-lld, adr, adr-short)
2. Add Postmortem template (Google SRE shape, "Where we got lucky")
3. Add Runbook template (operational, on-call format)
4. Adopt 4-gate spec review naming (Completeness / Evidence / Clarity / Consistency — adr-kit pattern)
5. Stable AI-friendly section headers across all templates (## Context / ## Decision / ## Consequences for ADR; analogous for others)
6. AGENTS.md + llms.txt sub-flow (plugin emits/syncs both at repo root)
7. Update SKILL.md decision tree + reference index for new templates
8. Run skill-creator eval baseline → improve → re-eval until stable
9. Commit each logical unit as separate `docs:` or `chore:` commit

## Tasks (in order)

| # | Task | Output | Commit |
|---|---|---|---|
| 1 | Snapshot skill to `.claude/skills/design-docs-workspace/skill-snapshot/` | snapshot dir | n/a |
| 2 | Fix `templates/bug-report.md` — add DRI metadata, Iteration Log section, Changelog, Design-Doc reference | bug-report.md | docs: bug-report template aligned to STANDARDS |
| 3 | Fix `templates/feature-lld.md` — add Type metadata, Changelog, Design-Doc/ADR refs | feature-lld.md | docs: feature-lld template aligned to STANDARDS |
| 4 | Rewrite `templates/adr.md` — Nygard-shape (Context/Decision/Status/Consequences), kill RFC vocab, add Changelog, fix status enum | adr.md | docs: adr template — Nygard format |
| 5 | Rewrite `templates/adr-short.md` — strip alternatives, fix enum, Context/Decision/Consequences | adr-short.md | (squashed with #4) |
| 6 | Add `templates/postmortem.md` — SRE shape | postmortem.md | docs: add postmortem template |
| 7 | Add `templates/runbook.md` — on-call ops | runbook.md | docs: add runbook template |
| 8 | Update `STANDARDS.md` — add Postmortem + Runbook required sections | STANDARDS.md | docs: STANDARDS — add postmortem + runbook |
| 9 | Add `references/spec-review-gates.md` — Completeness / Evidence / Clarity / Consistency | spec-review-gates.md | docs: 4-gate spec review |
| 10 | Update `SKILL.md` — new decision tree (Postmortem + Runbook routes), reference 4-gate review, AGENTS.md/llms.txt note | SKILL.md | docs: SKILL.md decision tree update |
| 11 | Add `templates/agents-md.md` + `templates/llms-txt.md` stubs + sub-flow guidance in SKILL.md | new templates | docs: AGENTS.md + llms.txt sync templates |
| 12 | Update `next_doc_number.sh` — add `postmortem` (no number, date-prefixed) | next_doc_number.sh | (squashed with #6) |
| 13 | Spec review pass on phase-5 plan + new templates | n/a | n/a |
| 14 | Skill-creator baseline eval — define scenarios, run, capture | iteration-1/ | n/a |
| 15 | Skill-creator improve cycle (max 3 iterations) | iteration-N/ | docs: SKILL.md eval-driven refinement |

## Track 2 Scope (deferred — separate session/plan)

- Extract `.claude/skills/design-docs/` to standalone repo `design-docs-claude/`
- Add `.claude-plugin/plugin.json`, README, LICENSE (MIT), CONTRIBUTING, examples
- Solo/team mode config toggle
- Python lint CLI (Refs: line + metadata + status enums)
- Bidirectional ADR↔code traceability (auto `DECISIONS.md` index + relationship types)
- Reader Testing sub-flow (fresh Claude reads back)
- Submit via `clau.de/plugin-directory-submission`

Track 2 starts after Track 1 ships and skill-creator eval shows stable scores across 5+ scenarios.

## Out of scope (this plan)

- Real-time progress dashboard (Pimzino-style WebSocket) — too heavy for v1
- Live mermaid preview MCP (veelenga) — separate plugin
- Plan→GitHub Issues converter (mattpocock to-issues) — bind via skills-registry, don't reimplement

## Success criteria

- [ ] All 4 existing templates pass spec review against STANDARDS.md
- [ ] Postmortem + Runbook templates present + spec-reviewed
- [ ] 4-gate spec-review reference doc + checklist
- [ ] AGENTS.md / llms.txt sub-flow documented in SKILL.md
- [ ] Stable AI-friendly headers across ADR + Bug Report (Context / Decision / Consequences for ADR; Observed / Root Cause / Fix / Iteration Log for Bug)
- [ ] Skill-creator baseline eval captured + at least 1 improvement cycle complete
- [ ] All changes shipped as `docs:` or `chore:` commits with `Refs:` to this plan

## Refs

- Memory: `project_phase_5_handoff.md`
- Audit findings: `.claude/skills/design-docs/templates/*.md` vs `docs/STANDARDS.md`
- Industry research: see this session's findings (4-tier taxonomy, AGENTS.md, llms.txt, adr-kit gates, Google SRE postmortems)
- Competitor research: 16 plugins surveyed; closest = SpillwaveSolutions/design-doc-mermaid, most popular = Pimzino/claude-code-spec-workflow, most rigorous = rvdbreemen/adr-kit

## Changelog

| Date | Change |
|---|---|
| 2026-05-06 | Initial draft |
