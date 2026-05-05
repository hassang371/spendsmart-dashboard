---
name: design-docs
description: Use when a feature, bug fix, or architectural decision needs a design document before code is written. Triggers for new Feature LLDs, Bug Reports, ADRs, Design Doc updates, and Mermaid diagrams.
---

# Design Documentation Skill

## Overview

Every code change must be preceded by documentation. This skill creates LLDs for features/bugs and maintains living Design Docs for system-wide architecture.

**Iron Law: No code without a design doc first.**

## Decision Tree

```
What are you building?
  → New feature              → Feature LLD       → templates/feature-lld.md
  → Bug fix                  → Bug report        → templates/bug-report.md
  → Architectural decision   → ADR               → templates/adr.md
  → System component update  → Design Doc        → docs/design/*.md
  → Need a diagram           → Mermaid guide     → references/mermaid/<type>.md
```

## Step 1: Get Doc Number

```bash
bash .claude/skills/design-docs/scripts/next_doc_number.sh features   # → 003
bash .claude/skills/design-docs/scripts/next_doc_number.sh bugs       # → BUG-001
bash .claude/skills/design-docs/scripts/next_doc_number.sh adr        # → ADR-001
```

## Step 2: Load Template

Read ONLY the template you need:

| Work type | Template | Output path |
|---|---|---|
| Feature | `templates/feature-lld.md` | `docs/features/NNN-name.md` |
| Bug fix | `templates/bug-report.md` | `docs/bugs/BUG-NNN-name.md` |
| ADR (architectural decision) | `templates/adr.md` | `docs/adr/ADR-NNN-name.md` |
| ADR — short form | `templates/adr-short.md` | `docs/adr/ADR-NNN-name.md` |
| System component | `templates/system-design-template.md`, `api-design-template.md`, or `database-design-template.md` | `docs/design/*.md` |

Fill ALL sections. No placeholders. No TODOs.

**Vocabulary:** "Design Doc" is the canonical term for living component-level architecture
(`docs/design/`). The deprecated term "HLD" is no longer used.

## Step 3: Add Mermaid Diagram (MANDATORY for non-trivial designs)

Every Feature LLD and Bug Report needs at least one diagram. ADRs and short-form ADRs are
optional. Load ONLY the guide you need:

| Diagram type | When | Load |
|---|---|---|
| Sequence | API flows, service interactions | `references/mermaid/sequence-diagrams.md` |
| Activity/Flowchart | Workflows, business logic | `references/mermaid/activity-diagrams.md` |
| Architecture | System components, C4 | `references/mermaid/architecture-diagrams.md` |
| Deployment | Infrastructure, Docker, cloud | `references/mermaid/deployment-diagrams.md` |
| Symbols | Unicode catalog | `references/mermaid/unicode-symbols.md` |

**Diagram validation workflow:** See `references/resilient-workflow.md`
**If diagram fails to render:** See `references/troubleshooting.md` (28 error fixes)

**Diagram style rules:**
1. Unicode symbols always (🔐 🌐 ⚙️ 💾 📬)
2. High-contrast colors (accessible)
3. Descriptive labels ("Auth Service (JWT)" not "Service A")

## Step 4: Design Doc Sync Check + Changelog

After any Feature LLD or Bug Report, check if a living Design Doc needs updating:

1. Read `references/hld-sync-protocol.md` (file name kept legacy; content is the Design Doc sync rule)
2. Identify affected Design Doc files in `docs/design/`
3. Update affected sections + add changelog entry at bottom

**All docs require a Changelog section** (Feature LLDs, Bug Reports, ADRs, Policies, Design Docs).
Add an entry when the doc is first written and whenever the implementation deviates from the
original design. See `docs/STANDARDS.md` for the required format per doc type.

## Step 4.5: Spec Review (MANDATORY)

After writing or updating ANY doc — before committing — run a spec review.

The skill bound to the spec-review situation lives in `.claude/skills-registry.md`. This
SKILL.md does NOT name the skill directly so plugin changes don't break this step.

**Lookup procedure:**
1. Open `.claude/skills-registry.md`
2. Find the row where situation = "Spec review on docs"
3. Use the bound skill via the Skill tool

**Review focus by doc type:**

| Doc type | Key checks for reviewer |
|---|---|
| Bug Report | Root cause backed by code evidence (file + line)? Steps reproducible? Fix description names exact files and functions? Test function named explicitly? Iteration log present if multi-attempt? |
| Feature LLD | Success criteria are measurable checkboxes (not prose)? All required sections per `docs/STANDARDS.md` present and filled? Security section non-empty? Edge cases concrete? |
| Design Doc | Accurate against codebase right now? No phantom endpoints or tables? Diagrams agree with actual code? Nothing documented that doesn't exist? |
| ADR | Decision is RECORDED, not deliberated (no long "Options Considered" without a chosen direction)? Consequences specific? Status clearly stated? |
| Policy | Rules are actionable (not vague)? Examples provided? Enforcement mechanism described? |

**Process:**

1. Invoke spec-review skill (per registry)
2. Fix all issues found
3. Re-invoke — repeat until reviewer finds no issues
4. Max 3 iterations; if still failing after 3, surface unresolved issues to user

**Block commit until spec review passes.** A doc with open review issues is not ready to commit.

## Step 5: Commit Docs Before Code

```bash
git add docs/
git commit -m "docs: add LLD for <feature-name>"
```

## Minimum Diagram Requirements

| Doc Type | Minimum |
|---|---|
| Feature LLD | 1 sequence or activity diagram |
| Bug report | 1 diagram showing bug's data flow |
| ADR (full) | 0–2 (optional — current state vs proposed if helpful) |
| ADR (short) | 0 |
| Design Doc | 3+ diagrams: architecture, data flow, deployment |

## Doc Standards

**Canonical standard:** `docs/STANDARDS.md` — required metadata, sections, status lifecycle, naming, Mermaid requirements.
Read this before filling in any template. It wins over all agent-specific guidance.

**ADR vs full ADR:** For routine architectural decisions, use `templates/adr-short.md`. For
significant decisions with multi-month consequences (data model, framework, deployment shape),
use `templates/adr.md`.

## Reference Index (load on demand — do NOT preload all)

| File | Load when |
|---|---|
| `docs/STANDARDS.md` | Before writing any doc — canonical required fields and sections |
| `references/doc-standards.md` | Need implementation notes specific to Claude (scripts, auto-numbering) |
| `references/hld-sync-protocol.md` | After writing any LLD (Design Doc sync rule, despite legacy filename) |
| `references/resilient-workflow.md` | Generating or validating diagrams |
| `references/troubleshooting.md` | Diagram fails to render |
| `references/mermaid/activity-diagrams.md` | Need workflow/process diagram |
| `references/mermaid/sequence-diagrams.md` | Need API/data flow diagram |
| `references/mermaid/architecture-diagrams.md` | Need component diagram |
| `references/mermaid/deployment-diagrams.md` | Need infrastructure diagram |
| `references/mermaid/unicode-symbols.md` | Need symbol reference |

## Scripts

| Script | Purpose | Usage |
|---|---|---|
| `scripts/next_doc_number.sh` | Auto-increment doc number | `bash scripts/next_doc_number.sh features` |
| `scripts/extract_mermaid.py` | Extract/validate diagrams | `python scripts/extract_mermaid.py doc.md --validate` |
| `scripts/resilient_diagram.py` | Generate + validate + save diagram | `python scripts/resilient_diagram.py --code "..." --title "flow"` |
| `scripts/mermaid_to_image.py` | Convert .mmd to PNG/SVG | `python scripts/mermaid_to_image.py diagram.mmd output.png` |

## Phase 5 deferred — skill iteration

This skill will be iterated using `skill-creator` (eval framework + variance analysis) in a
dedicated phase 5 session. Pending improvements:
- Encode the bug-iteration-loop pattern (one BUG-NNN doc spans iterations) into the bug-report template
- Add ADR templates with proper Status lifecycle
- Add ai-agent-friendly section templates with stable headers
- Run skill-creator eval to measure trigger accuracy
- Consider rename if a sharper name emerges
