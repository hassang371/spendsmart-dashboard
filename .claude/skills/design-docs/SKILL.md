---
name: design-docs
description: Use when a feature, bug fix, or architectural decision needs a design document before code is written. Triggers for new LLDs, bug reports, RFCs, HLD updates, and Mermaid diagrams.
---

# Design Documentation Skill

## Overview

Every code change must be preceded by documentation. This skill creates LLDs for features/bugs and maintains HLDs for system-wide architecture.

**Iron Law: No code without a design doc first.**

## Decision Tree

```
What are you building?
  → New feature        → Feature LLD    → templates/feature-lld.md
  → Bug fix            → Bug report     → templates/bug-report.md
  → Big decision       → RFC            → templates/rfc.md
  → System-wide doc    → HLD update     → docs/design/*.md
  → Need a diagram     → Mermaid guide  → references/mermaid/<type>.md
```

## Step 1: Get Doc Number

```bash
bash .claude/skills/design-docs/scripts/next_doc_number.sh features   # → 003
bash .claude/skills/design-docs/scripts/next_doc_number.sh bugs       # → BUG-001
bash .claude/skills/design-docs/scripts/next_doc_number.sh rfcs       # → RFC-001
```

## Step 2: Load Template

Read ONLY the template you need:

| Work type | Template | Output path |
|---|---|---|
| Feature | `templates/feature-lld.md` | `docs/features/NNN-name.md` |
| Bug fix | `templates/bug-report.md` | `docs/bugs/BUG-NNN-name.md` |
| RFC | `templates/rfc.md` | `docs/rfcs/RFC-NNN-name.md` |
| System doc | `templates/system-design.md` or `api-design.md` or `database-design.md` | `docs/design/*.md` |

Fill ALL sections. No placeholders. No TODOs.

## Step 3: Add Mermaid Diagram (MANDATORY)

Every doc needs at least one diagram. Load ONLY the guide you need:

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

## Step 4: HLD Sync Check + Changelog

After any LLD, check if HLD needs updating:

1. Read `references/hld-sync-protocol.md`
2. Identify affected HLD files in `docs/design/`
3. Update affected sections + add changelog entry at bottom

**All docs require a Changelog section** (Feature LLDs, Bug Reports, RFCs, Policies, HLDs).
Add an entry when the doc is first written and whenever the implementation deviates from the
original design. See `docs/STANDARDS.md` for the required format per doc type.

## Step 4.5: Spec Review (MANDATORY)

After writing or updating ANY doc — before committing — run a spec review.

**How:**

```
Dispatch the superpowers:code-reviewer agent with:
  - Full doc content
  - Doc type (Bug Report / Feature LLD / HLD / RFC / Policy)
  - Review focus (see table below)
  - Project context: SCALE is an AI-powered personal finance platform
    (FastAPI backend, Next.js frontend, Supabase Postgres, Celery workers)
```

**Review focus by doc type:**

| Doc type | Key checks for reviewer |
|---|---|
| Bug Report | Root cause backed by code evidence (file + line)? Steps reproducible? Fix description names exact files and functions? Test function named explicitly? |
| Feature LLD | Success criteria are measurable checkboxes (not prose)? All 11 required sections present and filled? Security section non-empty? Edge cases concrete? |
| HLD | Accurate against codebase right now? No phantom endpoints or tables? Diagrams agree with actual code? Nothing documented that doesn't exist? |
| RFC | Alternatives are genuine (not strawmen)? Impact fully assessed? Decision clearly stated with rationale? |
| Policy | Rules are actionable (not vague)? Examples provided? Enforcement mechanism described? |

**Process:**

1. Dispatch reviewer
2. Fix all issues found
3. Re-dispatch — repeat until reviewer finds no issues
4. Max 3 iterations; if still failing after 3, surface the unresolved issues to the user

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
| RFC | 2+ diagrams: current state + proposed state |
| HLD | 3+ diagrams: architecture, data flow, deployment |

## Doc Standards

**Canonical standard:** `docs/STANDARDS.md` — required metadata, sections, status lifecycle, naming, Mermaid requirements.
Read this before filling in any template. It wins over all agent-specific guidance.

**Short-form RFC:** For small decisions, use `templates/rfc-short.md` instead of `templates/rfc.md`.

## Reference Index (load on demand — do NOT preload all)

| File | Load when |
|---|---|
| `docs/STANDARDS.md` | Before writing any doc — canonical required fields and sections |
| `references/doc-standards.md` | Need implementation notes specific to Claude (scripts, auto-numbering) |
| `references/hld-sync-protocol.md` | After writing any LLD |
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
