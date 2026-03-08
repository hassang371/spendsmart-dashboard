# Doc Standards — Claude Implementation Notes

> **Canonical standard lives at `docs/STANDARDS.md`.**
> This file covers Claude-specific implementation details only.

## Auto-Numbering

Use the script to get the next doc number before creating any doc:

```bash
bash .claude/skills/design-docs/scripts/next_doc_number.sh features   # → 003
bash .claude/skills/design-docs/scripts/next_doc_number.sh bugs       # → BUG-002
bash .claude/skills/design-docs/scripts/next_doc_number.sh rfcs       # → RFC-002
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

Before committing any doc, verify:

- [ ] Metadata block at top (Doc ID, Date, Status, DRI)
- [ ] Status set to `Draft` or `Proposed`
- [ ] All required sections filled — no placeholders, no TODOs
- [ ] At least one Mermaid diagram (except RFC short-form)
- [ ] HLD sync check done (`references/hld-sync-protocol.md`)
- [ ] File committed before any code touches the repo

## Mermaid Help

- Diagram generation: `scripts/resilient_diagram.py`
- Rendering errors: `references/troubleshooting.md` (28 documented errors)
- Diagram guides: `references/mermaid/<type>.md`
