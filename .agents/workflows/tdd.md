---
description: how to follow test-driven development with red-green-refactor cycle
---

# Test-Driven Development

## When to Use

Use when implementing ANY feature, bugfix, or refactoring. Write the test FIRST.

## Core Principle

```
RED → GREEN → REFACTOR
```

No code without a failing test first. If code exists without a test, delete it and start over.

## Process

1. **Read** `.agents/skills/tdd/SKILL.md` for the full TDD framework
2. Follow the red-green-refactor cycle strictly
3. Reference `.agents/skills/tdd/references/testing-anti-patterns.md` to avoid common testing mistakes
4. Update `task.md` artifact after each completed cycle

## Anti-Patterns to Avoid

- Writing implementation before the test
- Testing implementation details instead of behavior
- Skipping the refactor step
- Writing tests that always pass
- "I'll add tests later" (you won't)
