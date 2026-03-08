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

## Commit Body (include doc reference when relevant)

```
feat: add transaction categorization confidence filter

Implements confidence threshold filtering for the categorization pipeline.
Refs: docs/features/002-confidence-filter.md
```

## After Verification Passes

Commit automatically — do not ask for permission after verification confirms everything works.
