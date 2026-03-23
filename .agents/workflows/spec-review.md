---
description: Run a spec review on a design document before committing. Use after writing any Feature LLD, Bug Report, RFC, HLD, or Policy doc. Replaces the vague "apply request-code-review to the doc" instruction.
---

# Spec Review

Run this after writing or updating ANY design document — before committing it.

**Purpose:** Catch issues in the document itself before the doc becomes the source of truth for implementation.

---

## Process

1. Re-read the full document you just wrote
2. Work through the **Universal Checklist** below, then the **doc-type checklist**
3. Fix every failing item
4. Re-read and re-check until all items pass
5. Commit the doc only after a clean pass

Max 3 iterations. If items still fail after 3, surface unresolved issues to the user before committing.

---

## Universal Checklist (all doc types)

- [ ] Metadata block present: Doc ID, Date, Status (`Draft`/`Proposed`), DRI
- [ ] All required sections filled — no TODOs, no placeholders, no "TBD"
- [ ] At least one Mermaid diagram (exception: RFC short-form)
- [ ] Changelog section present with at least one dated entry
- [ ] Every file path starts from project root (`apps/`, `packages/`, `docs/`)
- [ ] No phantom components, endpoints, tables, or services that don't exist in the codebase
- [ ] HLD delta noted: which `docs/design/*.md` files are affected by this change

---

## Feature LLD Checklist

- [ ] Success criteria are **measurable checkboxes**, not prose ("✅ API returns 200" not "endpoint works")
- [ ] All 11 required LLD sections present and filled (see `docs/STANDARDS.md`)
- [ ] Security section is non-empty — "N/A" is not acceptable without explicit justification
- [ ] Edge cases are concrete scenarios, not "handle edge cases"
- [ ] API changes reference exact FastAPI router path and function name
- [ ] Data model changes reference exact Supabase table and column names

---

## Bug Report Checklist

- [ ] Root cause is backed by code evidence: exact file path + line number
- [ ] Steps to reproduce are concrete and runnable by someone with zero context
- [ ] Fix description names the exact files and functions to change
- [ ] Test function is named explicitly (not "add a test" — name the function)
- [ ] Impact section states which users/flows are affected

---

## RFC Checklist

- [ ] At least 2 genuine alternative approaches (not strawmen)
- [ ] Impact fully assessed: data migrations, API changes, UI changes, perf
- [ ] Decision is clearly stated — not implied or buried in the rationale
- [ ] Rationale documented: why this option over the alternatives
- [ ] Reversibility assessed: is this decision easy to undo if wrong?

---

## HLD Checklist

- [ ] Accurately reflects the codebase **right now** — not aspirational
- [ ] No endpoints, tables, or services documented that don't exist yet
- [ ] Diagrams agree with actual code structure (run a quick spot-check)
- [ ] Changelog entry added for this update (what changed and why)
- [ ] Version number or date updated

---

## Policy Checklist

- [ ] Every rule is unambiguously actionable — a model can follow it without interpretation
- [ ] At least one concrete example per rule
- [ ] Enforcement mechanism described (how is this checked?)
- [ ] Scope is explicit: when does this policy apply, when doesn't it?
