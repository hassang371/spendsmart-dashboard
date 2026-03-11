# HLD Sync Protocol

## When to Update HLD

After writing or updating ANY LLD (feature, bug, RFC), check if HLD docs need updating.

### Sync Decision Tree

```
Did the LLD change...
  → Database schema? → Update docs/design/database-design.md
  → API endpoints? → Update docs/design/api-design.md
  → System components or architecture? → Update docs/design/system-architecture.md
  → Infrastructure or deployment? → Update docs/design/devops.md
  → Security model? → Update docs/design/security.md
  → None of the above? → No HLD update needed
```

Multiple HLD files may need updating from a single LLD.

## How to Update HLD

### 1. Locate the Affected Section

Read the HLD file. Find the section that relates to the LLD change.

### 2. Update Content

- Modify the section to reflect the **current** state (NOT "we added X" — just show what exists now)
- Update any affected Mermaid diagrams
- Keep the HLD as a snapshot of the current system, not a history log

### 3. Update Diagrams

If the change affects system topology, data flow, or deployment:

- Update the relevant Mermaid diagram in the HLD
- Ensure it matches the diagrams in the LLD
- Diagrams in the HLD should show the big picture; LLD diagrams show detail

### 4. Add Changelog Entry

At the bottom of the HLD file, add:

```markdown
## Changelog

| Date       | Feature          | Change                            |
| ---------- | ---------------- | --------------------------------- |
| YYYY-MM-DD | NNN-feature-name | Brief description of what changed |
```

## HLD Files

| File                                 | Covers                                                   |
| ------------------------------------ | -------------------------------------------------------- |
| `docs/design/system-architecture.md` | Overall system components, service boundaries, data flow |
| `docs/design/database-design.md`     | Schema, tables, relationships, migrations                |
| `docs/design/api-design.md`          | Endpoints, contracts, auth, versioning                   |
| `docs/design/devops.md`              | CI/CD, deployment, infrastructure, monitoring            |
| `docs/design/security.md`            | Auth flow, data protection, threat model                 |

## Important Rules

1. **HLD = current state.** Never use past tense. If something was removed, remove it from the HLD.
2. **LLD = point-in-time record.** LLDs are historical — they capture the design at the time of implementation.
3. **Diagrams must match.** If an LLD shows a sequence diagram involving Service A → Service B, and the HLD shows the architecture, both must agree on the service names and relationships.
4. **Don't bloat HLD.** The HLD is an overview. Detailed implementation goes in the LLD. The HLD links to relevant LLDs.
