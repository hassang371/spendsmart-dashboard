# Filesystem as Context

## Core Concept

The filesystem is a natural progressive disclosure mechanism. Store reference materials externally, load only when needed. File metadata (size, names, timestamps) provides context without loading content.

## Patterns

### Scratchpad Files

Write intermediate results to temporary files. Read back when needed. Keeps context lean while preserving access.

```
/tmp/debug-trace.md    — current debugging notes
/tmp/analysis.md       — intermediate analysis
```

### Structured Knowledge Files

Store domain knowledge in well-organized files:

```
.gemini/knowledge/     — reference docs loaded on demand
.gemini/tech-stack.md  — project tech context
.gemini/current_state.md — agent state
```

### Dynamic Discovery

Use file listing and search tools to discover relevant context at runtime instead of preloading. File sizes hint at complexity; naming conventions suggest purpose.

### Artifact Trail

Track modifications explicitly:

```markdown
## Files Modified

- src/auth.ts: Added JWT validation
- tests/auth.test.ts: New test for token expiry
```

## Guidelines

- Store externally, load on demand
- Use metadata for navigation (don't read entire directories)
- Maintain explicit file modification tracking
- Use consistent naming for discoverability
- Clean up scratch files after use
