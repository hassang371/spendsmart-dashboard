# Commit Strategy

## Conventional Commit Prefixes

| Prefix | When |
|---|---|
| `docs:` | Documentation only (LLD, HLD, RFC) |
| `feat:` | New feature implementation |
| `fix:` | Bug fix |
| `test:` | Adding or updating tests |
| `refactor:` | Code restructuring, no behavior change |
| `chore:` | Maintenance (deps, config, HLD sync) |

## When to Commit

- After design docs are written — before any code
- After each logical unit of implementation
- After HLD sync at the end of a feature
- Mid-feature commits are fine if a sub-task is independently useful

## Mandatory Doc Reference (enforced for fix: and feat:)

Every `fix:` commit MUST reference a Bug Report:

```
fix: write user_model_metadata after adapter training

Upserts user_model_metadata on training completion so the classifier
can discover the adapter URL on next request.
Refs: docs/bugs/BUG-002-linear-adapter-broken-pipeline.md
```

Every `feat:` commit MUST reference a Feature LLD or RFC:

```
feat: add transaction categorization confidence filter

Implements confidence threshold filtering for the categorization pipeline.
Refs: docs/features/002-confidence-filter.md
```

**No Refs: = orphan commit.** A `fix:` or `feat:` commit with no `Refs:` line pointing to a
real file in `docs/` is NOT ALLOWED. If no doc exists yet, create it first.

`refactor:`, `test:`, `chore:`, `docs:` commits: `Refs:` is optional but recommended.

## Pre-Commit: Update Doc Status

Before the final feature/bug/RFC commit, update the design doc's `Status` field:

| Code state | Doc status to set |
|---|---|
| Implementation complete, about to commit | `Implemented` |
| Verification passed (tests green, evidence confirmed) | `Verified` |

Commit the status update **before or alongside** the code commit — never after.

```
docs: update RFC-001 status to Implemented
feat: implement RFC-001 — ...
```

Or combined: update status in the doc, then commit both together.

## After Verification Passes

Commit automatically — do not ask for permission after verification confirms everything works.
