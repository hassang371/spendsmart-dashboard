---
name: design-docs
description: Use when a feature, bug fix, architectural decision, incident postmortem, operational runbook, or component-level architecture update needs a written design document before code is written or shipped. Triggers for new Feature LLDs, Bug Reports, ADRs, Postmortems, Runbooks, Design Doc updates, AGENTS.md / llms.txt sync, and Mermaid diagrams. Invoke this skill whenever the user mentions designing a feature, fixing a bug, recording a decision, writing up an incident, drafting a runbook, updating architecture diagrams, or producing any technical documentation — even if they don't explicitly say "design doc".
---

# Design Documentation Skill

## Overview

Every code change is preceded by documentation. This skill creates typed docs (Feature LLD, Bug Report, ADR, Postmortem, Runbook) and maintains living Design Docs for system-wide architecture.

**Iron Law: No code without a design doc first.**

## Decision Tree

```
What are you producing?
  → New feature                  → Feature LLD       → templates/feature-lld.md
  → Bug fix                      → Bug Report        → templates/bug-report.md
  → Architectural decision       → ADR               → templates/adr.md (or adr-short.md)
  → Incident write-up            → Postmortem        → templates/postmortem.md
  → On-call operational guide    → Runbook           → templates/runbook.md
  → System component update      → Design Doc        → docs/design/*.md
  → Cross-tool agent context     → AGENTS.md sync    → templates/agents-md.md
  → External LLM doc index       → llms.txt sync     → templates/llms-txt.md
  → Need a diagram               → Mermaid guide     → references/mermaid/<type>.md
```

## Step 1: Get Doc Number / ID

```bash
bash .claude/skills/design-docs/scripts/next_doc_number.sh features    # → 003
bash .claude/skills/design-docs/scripts/next_doc_number.sh bugs        # → BUG-001
bash .claude/skills/design-docs/scripts/next_doc_number.sh adr         # → ADR-001
bash .claude/skills/design-docs/scripts/next_doc_number.sh research    # → 001
bash .claude/skills/design-docs/scripts/next_doc_number.sh postmortem  # → POSTMORTEM-2026-05-06
```

Runbooks are not numbered — name describes the alert/symptom (`RUNBOOK-celery-queue-backlog.md`).

## Step 2: Load Template

Read ONLY the template you need:

| Work type | Template | Output path |
|-----------|----------|-------------|
| Feature | `templates/feature-lld.md` | `docs/features/NNN-name.md` |
| Bug fix | `templates/bug-report.md` | `docs/bugs/BUG-NNN-name.md` |
| ADR (architectural decision) | `templates/adr.md` | `docs/adr/ADR-NNN-name.md` |
| ADR — short form | `templates/adr-short.md` | `docs/adr/ADR-NNN-name.md` |
| Postmortem | `templates/postmortem.md` | `docs/postmortems/POSTMORTEM-YYYY-MM-DD-name.md` |
| Runbook | `templates/runbook.md` | `docs/runbooks/RUNBOOK-name.md` |
| System component | `templates/system-design-template.md`, `api-design-template.md`, or `database-design-template.md` | `docs/design/*.md` |
| AGENTS.md | `templates/agents-md.md` | `AGENTS.md` (repo root) |
| llms.txt | `templates/llms-txt.md` | `llms.txt` (site root) |

Fill ALL sections. No placeholders. No TODOs.

**Vocabulary:**
- "Design Doc" is the canonical term for living component-level architecture (`docs/design/`). The deprecated term "HLD" is no longer used.
- "ADR" records a decision that has been made. RFC vocabulary is not used — if you find yourself writing a long "Options Considered" section, you wrote an RFC. Decide first, then record.

## Step 3: Add Mermaid Diagram

Per `docs/STANDARDS.md`:

| Doc Type | Minimum |
|----------|---------|
| Feature LLD | 1 (sequence or activity) |
| Bug Report | 1 (sequence showing bug data path) |
| Postmortem | 1 (failure path: trigger → system → users) |
| ADR | 0–1 (current → proposed if architecture change) |
| ADR (short) | 0 |
| Runbook | 0 |
| Design Doc | 3+ (architecture + data flow + deployment) |

Load ONLY the guide you need:

| Diagram type | When | Load |
|-------------|------|------|
| Sequence | API flows, service interactions, bug paths, failure paths | `references/mermaid/sequence-diagrams.md` |
| Activity/Flowchart | Workflows, business logic | `references/mermaid/activity-diagrams.md` |
| Architecture | System components, C4 | `references/mermaid/architecture-diagrams.md` |
| Deployment | Infrastructure, Docker, cloud | `references/mermaid/deployment-diagrams.md` |
| Symbols | Unicode catalog | `references/mermaid/unicode-symbols.md` |

**Diagram validation workflow:** `references/resilient-workflow.md`
**If diagram fails to render:** `references/troubleshooting.md` (28 known errors)

**Diagram style rules:**
1. Unicode symbols always (🔐 🌐 ⚙️ 💾 📬 👤)
2. High-contrast colors (accessible)
3. Descriptive labels ("Auth Service (JWT)" not "Service A")

## Step 4: Design Doc Sync Check + Changelog

After any Feature LLD, Bug Report, or Postmortem, check if a living Design Doc needs updating:

1. Read `references/design-doc-sync-protocol.md`
2. Identify affected Design Doc files in `docs/design/`
3. Update affected sections + add changelog entry at bottom

After any major doc change (new doc type, new convention, new command), check if `AGENTS.md` and `llms.txt` need updating:

1. Read `references/agents-md-llms-txt.md`
2. Update AGENTS.md if a new agent-relevant convention was added
3. Update llms.txt entries if architecture or public docs changed

**All docs require a Changelog section** (Feature LLDs, Bug Reports, ADRs, Postmortems, Runbooks, Design Docs, Policies). Add an entry on creation and on every status transition or material edit. See `docs/STANDARDS.md` for the required format per doc type.

## Step 4.5: Spec Review — Four Gates (MANDATORY)

After writing or updating ANY doc — before committing — run a spec review against four named gates.

The skill bound to the spec-review situation lives in `.claude/skills-registry.md`. This SKILL.md does NOT name the skill directly so plugin changes don't break this step.

**Lookup procedure:**
1. Open `.claude/skills-registry.md`
2. Find the row where situation = "Spec review on docs"
3. Use the bound skill via the Skill tool, passing the four-gate reference

**The four gates** (full detail in `references/spec-review-gates.md`):

| # | Gate | What it checks |
|---|------|----------------|
| 1 | **Completeness** | All required sections present and filled — no `TBD`, no empty tables |
| 2 | **Evidence** | Every claim has a backing artifact (file:line, benchmark, log, citation) |
| 3 | **Clarity** | A fresh reader can act on the doc without prior conversation context |
| 4 | **Consistency** | Doc agrees with itself, peer docs, and current code |

**Review focus by doc type:**

| Doc type | Key checks for reviewer |
|----------|------------------------|
| Bug Report | Root cause cites file:line. Steps reproducible. Fix names exact files/functions. Test function named explicitly. **Iteration Log present** even if only one iteration. |
| Feature LLD | Success criteria are measurable checkboxes (not prose). All required sections present. Security section non-empty. Edge cases concrete. |
| ADR | Decision is RECORDED, not deliberated. Context cites the forcing constraint. Consequences specific (positive + negative + commitment). No long "Options Considered" without a chosen direction. |
| Postmortem | Blameless (roles, not names). **"Where We Got Lucky" section present** — highest-signal section. Action items have owners + due dates. Timeline uses real timestamps. |
| Runbook | 3am-friendly. Quick Reference one-liner exists. Mitigation steps are exact commands. Escalation path concrete. |
| Design Doc | Accurate against codebase right now. No phantom endpoints or tables. Diagrams agree with actual code. Nothing documented that doesn't exist. |
| Policy | Rules actionable (not vague). Examples provided. Enforcement mechanism described. |

**Process:**

1. Invoke spec-review skill (per registry), passing the four-gate reference
2. Fix all issues found, naming the failing gate ("Gate 2 fails — root cause has no file:line citation")
3. Re-invoke until all gates pass
4. Max 3 iterations; if still failing after 3, surface unresolved issues to user — the doc may need design rework

**Block commit until spec review passes.** A doc with open review issues is not ready to commit.

**Scratch carve-out:** Step 4.5 is mandatory for any doc destined for `docs/` and a commit. Eval outputs, spike notes, and other scratch artifacts under `.claude/skills/*-workspace/` may skip review — but they must be deleted or promoted to `docs/` (with full review) before any code references them.

## Step 5: Commit Docs Before Code

```bash
git add docs/
git commit -m "docs: add LLD for <feature-name>"
```

For bug fixes, no `fix:` commit until the user explicitly confirms the bug is resolved. Use `wip:` during iteration. See `.claude/rules/commit-strategy.md`.

## Doc Standards

**Canonical standard:** `docs/STANDARDS.md` — required metadata, sections, status lifecycle, naming, Mermaid requirements. Read this before filling in any template. It wins over all agent-specific guidance.

**ADR vs short ADR:** For routine architectural decisions, use `templates/adr-short.md`. For significant decisions with multi-month consequences (data model, framework, deployment shape), use `templates/adr.md`.

## Reference Index (load on demand — do NOT preload all)

| File | Load when |
|------|-----------|
| `docs/STANDARDS.md` | Before writing any doc — canonical required fields and sections |
| `references/spec-review-gates.md` | Running spec review (Step 4.5) |
| `references/doc-standards.md` | Need implementation notes specific to Claude (scripts, auto-numbering) |
| `references/design-doc-sync-protocol.md` | After writing any LLD or Bug Report — Design Doc sync rule |
| `references/agents-md-llms-txt.md` | Initializing or syncing AGENTS.md / llms.txt |
| `references/resilient-workflow.md` | Generating or validating diagrams |
| `references/troubleshooting.md` | Diagram fails to render |
| `references/mermaid/activity-diagrams.md` | Need workflow/process diagram |
| `references/mermaid/sequence-diagrams.md` | Need API/data flow diagram |
| `references/mermaid/architecture-diagrams.md` | Need component diagram |
| `references/mermaid/deployment-diagrams.md` | Need infrastructure diagram |
| `references/mermaid/unicode-symbols.md` | Need symbol reference |

## Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/next_doc_number.sh` | Auto-increment doc number / emit date prefix | `bash scripts/next_doc_number.sh features\|bugs\|adr\|research\|postmortem` |
| `scripts/extract_mermaid.py` | Extract/validate diagrams | `python scripts/extract_mermaid.py doc.md --validate` |
| `scripts/resilient_diagram.py` | Generate + validate + save diagram | `python scripts/resilient_diagram.py --code "..." --title "flow"` |
| `scripts/mermaid_to_image.py` | Convert .mmd to PNG/SVG | `python scripts/mermaid_to_image.py diagram.mmd output.png` |

## Pitfall rules (industry-research-derived)

1. **ADR is RECORDED, not deliberated.** Long "Options Considered" weighing alternatives without a chosen direction = RFC, not ADR. Use `mattpocock-skills:grill-with-docs` or `superpowers:brainstorming` to decide first; record after.
2. **LLD vs Plan no-overlap.** LLD = WHAT to build (design, contracts, edge cases). Plan = HOW + ORDER (steps, dependencies, sequencing). A Plan re-stating LLD design content is doing the wrong thing.
3. **Bug iteration loop = one doc spans attempts.** Don't create BUG-001-attempt-1, BUG-001-attempt-2. One BUG-NNN doc, append Iteration Log entries, `fix:` only after user confirms.
4. **Postmortems are blameless.** Refer to roles ("the on-call engineer"), never names. The "Where We Got Lucky" section surfaces near-miss risks — highest-signal section.
5. **Runbooks rot fastest.** Update after every incident the runbook was used in. Mark `Outdated` if the system changed materially without runbook update.
6. **Design Docs are LIVING.** Sync them in the same commit as the feature, not in a follow-up PR. Use the changelog to record deviations from the original design.

## Phase 5 — public plugin extraction (deferred)

This skill is being extracted into a standalone Claude Code plugin (`design-docs-claude`) for public use. Pending work tracked in `docs/plans/2026-05-06-phase-5-design-docs-iteration.md`. Until extraction ships, this is the project-internal skill. Plugin extraction adds:

- Solo / team mode config toggle
- Python lint CLI (Refs:, metadata, status enums) for CI
- Bidirectional ADR↔code traceability (`DECISIONS.md` index, relationship types)
- Reader Testing sub-flow (fresh Claude reads back doc)
- Submission to clau.de plugin marketplace
