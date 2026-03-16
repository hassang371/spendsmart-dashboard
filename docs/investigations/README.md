# Investigations — Scratch Pad

Lightweight scratch notes for research findings that are not yet confirmed bugs or features.

## Rules

- Notes here are **unreviewed and informal** — no required sections, no Mermaid diagrams
- Notes here are **never committed as formal docs** — they are working memory only
- Once a finding is **confirmed**, it graduates:
  - Confirmed defect → `docs/bugs/BUG-NNN-name.md`
  - Confirmed missing feature → `docs/features/NNN-name.md` (only if user approves building it)
- This directory should stay nearly empty — findings should graduate quickly

## Format (suggested, not required)

```
## Finding: <short description>
Date: YYYY-MM-DD
Status: Unconfirmed | Confirmed | Graduated to BUG-NNN

What I observed:
...

What I suspect:
...

Next step to confirm:
...
```
