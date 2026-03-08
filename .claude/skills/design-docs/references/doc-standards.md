# Documentation Standards

## What Good Documentation Looks Like

### Feature LLD (Low-Level Design)

A feature LLD is a self-contained document that answers:

- **What** are we building? (scope, boundaries)
- **Why** are we building it? (user problem, business value)
- **How** does it work? (data flow, API contracts, state changes)
- **What could go wrong?** (edge cases, failure modes, security)
- **How do we know it works?** (acceptance criteria, test strategy)

**Quality checklist:**

- [ ] Has a clear problem statement
- [ ] Defines explicit success criteria
- [ ] Contains at least one Mermaid diagram
- [ ] Lists all affected components/files
- [ ] Identifies edge cases and error scenarios
- [ ] Specifies the testing approach
- [ ] No TODO placeholders — every section is filled

### HLD (High-Level Design)

An HLD is a living document that represents the **current** state of a system component. It is NOT a historical record — it always reflects reality.

**HLD properties:**

- One HLD per system domain (architecture, database, API, devops)
- Updated every time a feature LLD changes something in that domain
- Contains overview diagrams showing the big picture
- Has a changelog at the bottom tracking when/why it was updated

**Quality checklist:**

- [ ] Reflects the CURRENT system state (not historical)
- [ ] Has architecture/ER/deployment diagrams
- [ ] Each section has enough detail for a new developer to understand
- [ ] Changelog is maintained at the bottom

### Bug Reports

A bug report documents:

- **Observed behavior** (what happened)
- **Expected behavior** (what should happen)
- **Root cause** (why it happened — found during debugging)
- **Fix description** (what changed)
- **Regression prevention** (test added)

### RFCs

An RFC proposes a significant change and gets approval before implementation:

- **Problem statement** — what needs solving
- **Proposed solution** — with diagrams
- **Alternatives considered** — what was rejected and why
- **DRI** (Directly Responsible Individual) — who owns this
- **Impact assessment** — what changes, what breaks
- **Decision** — approved/rejected with rationale

## Writing Style

1. **Be specific** — "Increases latency by ~200ms" not "might be slower"
2. **Use diagrams** — A picture is worth a thousand tokens
3. **Show data flow** — How data enters, transforms, and exits
4. **Name things** — Concrete function/table/endpoint names, not abstractions
5. **Version awareness** — Reference specific versions, commits, or dates
