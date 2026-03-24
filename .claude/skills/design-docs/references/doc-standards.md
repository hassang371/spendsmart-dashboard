# Doc Standards — Claude Implementation Notes

> **Canonical standard lives at `docs/STANDARDS.md`.**
> This file covers Claude-specific implementation details only.

## Auto-Numbering

Use the script to get the next doc number before creating any doc:

```bash
bash .claude/skills/design-docs/scripts/next_doc_number.sh features   # → returns next available (e.g., 008)
bash .claude/skills/design-docs/scripts/next_doc_number.sh bugs       # → returns next available (e.g., BUG-014)
bash .claude/skills/design-docs/scripts/next_doc_number.sh rfcs       # → returns next available (e.g., RFC-001)
```

## Template Selection

| Situation | Template |
|---|---|
| New feature | `templates/feature-lld.md` |
| Bug fix | `templates/bug-report.md` |
| Significant architectural/process decision | `templates/rfc.md` |
| Small decision (≤4 sections) | `templates/rfc-short.md` |
| System-wide HLD | `templates/system-design-template.md` / `api-design-template.md` / `database-design-template.md` |

## Quality Checklist (Claude)

Before committing any doc, verify ALL of:

- [ ] Metadata block at top (Doc ID, Date, Status, DRI)
- [ ] Status set to `Draft` or `Proposed`
- [ ] All required sections filled — no placeholders, no TODOs
- [ ] At least one Mermaid diagram (except RFC short-form)
- [ ] Changelog section present with at least one entry
- [ ] HLD sync check done (`references/hld-sync-protocol.md`)
- [ ] **Spec review passed** (`superpowers:code-reviewer` dispatched, issues fixed, re-reviewed clean)
- [ ] File committed before any code touches the repo

## Mermaid Help

- Diagram generation: `scripts/resilient_diagram.py`
- Rendering errors: `references/troubleshooting.md` (28 documented errors)
- Diagram guides: `references/mermaid/<type>.md`
