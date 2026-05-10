# Canon-Frozen Guard

This rule is auto-loaded every session. It defines when Claude must STOP and ask the user before committing to a canon-frozen design doc.

The Canon-Frozen Guard is the agent-side companion to LLD-006-r4 § narrow change. The lint check L2 (`cli.lint --pre-commit`) catches violations mechanically; this rule prevents the agent from triggering them in the first place.

## When this fires

ANY of these → STOP, surface to user with options:

1. About to `git add` or `git commit` a `.md` file under refs-eligible prefix (`docs/{features,bugs,adr,design,postmortems,runbooks}/`)
2. AND the prior committed state of that file (i.e., `git show HEAD:<path>`) has Status field ∈ canon-frozen-statuses `{Approved, Implemented, Verified, Fix Applied, Current}`
3. AND the diff includes ANY change outside whitelist `{Status, Iteration, Superseded by}` frontmatter fields and append-only Changelog rows

If all three true → fire interview-gate. Show user:
- Summary of what changed
- Status field at HEAD (canon-frozen value)
- Two paths: narrow-change (only if change is whitelist-eligible — usually means the change was incorrectly scoped) OR supersession (archive + new -rN.md per LLD-006-r4)
- Recommend supersession with one-line reason

## What is canon-frozen

Per orchestra LLD-006-r4 Glossary § canon-frozen statuses:

```
{Approved, Implemented, Verified, Fix Applied, Current}
```

These statuses indicate the doc represents a committed contract (architectural decision, shipped feature, verified bug fix, or operational reference). Body edits to canon-frozen docs silently rewrite contracts that other commits' `Refs:` lines point at.

## What's permitted (narrow-change whitelist)

Three permitted edit types on canon-frozen:

1. **Frontmatter field flip** — `Status`, `Iteration`, `Superseded by` fields only. Anything else forbidden.
2. **Changelog append** — adding NEW rows to the Changelog table. Existing rows must remain byte-identical.
3. **Both 1 and 2 in one commit** — common for status transitions (e.g., Status flip + corresponding Changelog entry)

ANYTHING else — section heading edited, paragraph rewritten, code snippet updated, Acceptance item changed, table row modified — is a non-narrow change. Supersession workflow required.

## What's required (supersession workflow)

If the change is non-narrow:

1. `git mv docs/<type>/<doc>.md docs/archive/<type>/<doc>.md`
2. Edit archived file:
   - `> **Status:** Rejected`
   - Add `> **Reason:** <one line: what was found, why supersession needed; reference attestation path>`
   - Add `> **Superseded by:** docs/<type>/<doc>-r<N+1>.md`
3. `cp docs/archive/<type>/<doc>.md docs/<type>/<doc>-r<N+1>.md` (or write fresh)
4. Edit new file:
   - `> **Status:** Draft` (full edit allowed)
   - `> **Iteration:** <N+1>`
   - `> **Supersedes:** docs/archive/<type>/<doc>.md`
   - Apply substantive changes
5. Run spec-review on new file → produces fresh attestation
6. After re-attestation passes, flip Status: Draft → Implemented (or Verified, Current, etc.)
7. `python -m cli.lifecycle update-attestation-paths --reviews <prior-attestation-paths>` to rewrite old attestations' `doc_subject.path` → archive path
8. Single `feat:` commit with `Refs: docs/<type>/<doc>-r<N+1>.md`

Procedural reference: `docs/runbooks/RUNBOOK-canon-inplace-violation-recovery.md` (orchestra repo).

## Tiered exception (BUG-011 — when shipped)

Per orchestra BUG-011 (status: Implemented; tracking tiered supersession refinement; ships in v1.7+), the strict-binary rule may be relaxed for non-Critical findings:

| Finding severity driving change | Permitted edit |
|---|---|
| **Critical** | Supersession REQUIRED (no exception) |
| **Important** | Author judgment: ≤3 findings = narrow-change with `Addresses:` commit-msg lines + Changelog row per finding; 4+ = supersession |
| **Minor** | Narrow-change body edit + `Addresses:` commit-msg lines + Changelog row per finding |

Until BUG-011 ships in orchestra v1.7+, the strict-binary rule applies — supersession for ANY non-whitelist body change on canon-frozen.

This rule (canon-frozen-guard) follows orchestra version: when v1.7+ tiered rule ships, this rule will be updated to encode the tiered logic.

## What is NOT a trigger (proceed silently)

- Editing a Status: Draft doc (Draft permits full edit; supersession only on Rejected)
- Adding new file under `docs/<type>/` (no prior — no canon to violate)
- Editing `docs/plans/` files (plans are not canon-frozen by convention; edit freely until project pivots)
- Editing `docs/reviews/*.review.yaml` (attestations are immutable audit records but not subject to L2 — exception: never edit committed attestations)
- Editing files outside `docs/` (code, tests, configs, READMEs)
- Whitelist-only edit (Status/Iteration/Superseded by + Changelog append)

## Anti-patterns

| Anti-pattern | Why bad | Fix |
|---|---|---|
| "Just one wording fix" on canon-frozen | All wording fixes are body edits → strict-binary requires supersession | Either narrow-change-eligible (no — wording is not whitelist) → supersession |
| Bumping Iteration to "make the diff fit" | Iteration is whitelist but body change still violates | Iteration bump alone OK; body change requires supersession |
| Adding Changelog entry "explaining" the body change | Changelog is append-only WHITELIST; body change still violates regardless of changelog entry | Supersession |
| Skipping spec-review on canon-frozen because "it's already Implemented" | Even minor wording can drift from code → spec-review catches it | Run spec-review on supersession-iteration before flipping Status |
| Renaming file to bypass L2 (different path = no diff) | L4 doc-id-burn check catches this | Use proper supersession (-rN suffix is the sanctioned rename path) |

## Examples

### GOOD — Status flip + Changelog (whitelist)

> User: "mark BUG-005 as Fix Applied"
> Me: [edit Status: Investigating → Fix Applied; add Changelog row noting status transition + commit hash that closed it; commit `chore: BUG-005 → Fix Applied`]

No interview gate fires. Whitelist edits + append-only Changelog. L2 passes.

### GOOD — Iteration bump for re-attestation

> User: "run spec-review on LLD-007 again"
> Me: [bump Iteration N → N+1 frontmatter; commit `docs: LLD-007 iteration bump for r{N+1} attestation`; run /orchestra:spec-review]

Whitelist-only. L2 passes. Attestation produced with matching iteration field.

### BAD — wording fix on canon-frozen

> User: "fix the typo in LLD-007 Acceptance section"
> Me (WRONG): [edit Acceptance text; commit `fix: typo in LLD-007`]

Interview gate FIRES. Status: Implemented = canon-frozen. Acceptance edit is body content. STOP and ask:
1. Supersession (archive + -rN.md with typo fix) — heavy for one typo
2. Defer to next supersession event (batch with other findings)
3. (When BUG-011 v1.7+ ships) narrow-change with `Addresses: <attestation-path> finding (Minor)` + Changelog row

### BAD — section rewrite

> User: "update the Design section in LLD-005 — architecture changed"
> Me (WRONG): [edit Design section; commit `docs: update LLD-005 Design`]

Interview gate FIRES. Architectural change on canon-frozen → supersession REQUIRED (Critical-finding tier). No exception.

## Relationship to other gates

- **Gate 1 (Discovery)** — fires when investigation surfaces a defect. Canon-Frozen Guard fires when committing a fix; both can stack
- **Gate 2 (Design)** — design doc must exist before code. Canon-Frozen Guard fires when editing already-canon design doc
- **Gate 3 (Spec Review)** — must run on every doc edit. Canon-Frozen Guard prevents in-place edit; spec-review runs on the supersession file
- **Gate 4 (Commit)** — Refs: line on fix:/feat: commits. After supersession, Refs: points to new -rN.md path (not the archived original)
- **Gate 5 (Implementation Sync)** — design-doc deviations recorded in Changelog. Changelog append IS whitelist-eligible; deviation entries on canon-frozen are permitted

## Why this rule exists

Direct lineage: orchestra POSTMORTEM-2026-05-10-canon-inplace-violation. Agent body-edited canon-frozen LLD-007 in commits `653db4e` + `bc359e7` instead of routing through supersession. Three enforcement layers all failed:

1. `cli.lint --commit` runs only L1 (BUG-009 closes this gap)
2. orchestra repo has no pre-commit hook installed (BUG-010 closes this gap)
3. Agent self-check missed Interview Gate trigger ("silent design decision")

This rule (Canon-Frozen Guard) is the agent-side primitive for #3. BUG-009 + BUG-010 close #1 and #2 mechanically. Combined: 3-layer defense against canon-inplace violations.

## Scope: SCALE-side only (for now)

This rule lives at `.claude/rules/canon-frozen-guard.md` in the SCALE repo. Loaded automatically by the agent during SCALE sessions.

orchestra-side integration deferred to **workflow skill v2.0+** per LLD-011 roadmap. Once orchestra ships its workflow skill, this rule will be auto-generated into consumer repos via `cli.init` template (same pattern as Interview Gate v1.5.1).

Until then: SCALE only. Other consumers manually copy this rule if they want the same protection.

## What this rule does NOT do

- Replace mechanical lint checks (L2 in pre-commit hook). Rule is agent-discipline; lint is enforcement
- Define the supersession workflow itself (that lives in LLD-006-r4 + RUNBOOK-canon-inplace-violation-recovery)
- Override LLD-006-r4 § narrow change. Rule encodes the same logic as a pre-commit-time agent check

## Updating this rule

- When orchestra ships v1.7+ BUG-011 tiered supersession → update the Tiered exception table in this rule to remove the "when shipped" caveat
- When orchestra workflow skill v2.0+ ships → migrate this rule to orchestra template; SCALE consumes via `cli.init`
- When canon-frozen statuses set changes (LLD-006-r5+) → update the canon-frozen list
