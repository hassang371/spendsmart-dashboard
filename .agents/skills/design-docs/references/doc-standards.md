# Documentation Templates & Quality

> **NOTE:** The canonical standards for document content, required sections, and status lifecycles live in `docs/STANDARDS.md`.
> **Always read `docs/STANDARDS.md` first.** This file only contains agent-specific implementation notes for generating docs.

---

## 1. Auto-Numbering Script

Always use `scripts/next_doc_number.sh <type>` to generate the correct three-digit ID before creating a new design document.

- Feature LLDs: `bash scripts/next_doc_number.sh features` → returns e.g. `003`
- Bug Reports: `bash scripts/next_doc_number.sh bugs` → returns e.g. `BUG-007`
- RFCs: `bash scripts/next_doc_number.sh rfcs` → returns e.g. `RFC-002`

Use the precise output of this script in the filename and the metadata block `Doc ID` field.

---

## 2. Template Selection Guide

When deciding between the two RFC templates:
- Use `rfc.md` (Full) ONLY for major architectural shifts involving multiple components, entirely new databases, or sweeping infrastructure changes.
- Use `rfc-short.md` (Short) for localized technical decisions, library choices, localized refactors, or policy adoptions.

---

## 3. Gemini Quality Checklist for Generation

When writing Feature LLDs, Bug Reports, or RFCs as an agent, strictly verify:

1. **Precision:** Never write "will be implemented later" or use `TODO`. Either define it, or assign a specific name/date for resolution.
2. **Path Absolute:** Always reference files inside the `apps/` or `packages/` workspace using absolute or relative paths starting from the project root.
3. **Diagram Integrity:** Ensure all Mermaid diagrams have matching aliases/participants that align with the actual code class/module names. Do not invent arbitrary conceptual blocks if they don't map to code.
4. **HLD Delta:** Every Feature LLD or Bug Report *must* conclude by explicitly listing which HLD files (in `docs/design/`) are affected by this change, preparing for Step 5a of the Docs-Driven Dev workflow.
5. **Changelog Section:** Every doc (Feature LLD, Bug Report, RFC, Policy, HLD) must include a Changelog section with at least one entry (creation date + initial status).
6. **Spec Review Passed:** Before committing, read `spec-review.md` and work through its checklists. Fix all issues. Do not commit a doc with open review items.
