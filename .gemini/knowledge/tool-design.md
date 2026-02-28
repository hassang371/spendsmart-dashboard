# Tool Design Principles

## Core Concept

Tool definitions steer agent behavior more than system prompts. Poor descriptions force guessing; optimized descriptions include usage context, examples, and defaults.

## The Consolidation Principle

If a human engineer cannot definitively say which tool to use in a given situation, an agent cannot either. Consolidate overlapping tools.

## Design Guidelines

### Naming

- Use clear, action-oriented names (`read_file`, `search_code`, not `utility1`)
- Consistent naming conventions across tool sets
- Names should imply scope and side effects

### Descriptions

- Include WHEN to use (not just what it does)
- Specify what it returns
- Include common use cases
- Note limitations and edge cases

### Parameters

- Required parameters should be truly required
- Provide sensible defaults for optional parameters
- Use enums instead of free-text where possible
- Include format examples for complex inputs

### Error Context

Return actionable error messages:

```
❌ "Error: invalid input"
✅ "Error: file_path must be absolute (received 'src/app.ts'). Use '/Users/project/src/app.ts'"
```

## Format Options

- Return structured data (JSON) for programmatic use
- Return human-readable format for reasoning
- Let the agent specify preferred format when possible

## Anti-Patterns

- Too many similar tools (consolidate)
- Vague descriptions ("does stuff with files")
- Missing error context
- No usage examples in description
- Requiring complex input formats without examples
