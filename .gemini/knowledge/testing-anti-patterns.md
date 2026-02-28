# Testing Anti-Patterns

**Load this when:** writing or changing tests, adding mocks, or tempted to add test-only methods to production code.

## The Iron Laws

1. NEVER test mock behavior
2. NEVER add test-only methods to production classes
3. NEVER mock without understanding dependencies

## Anti-Pattern 1: Testing Mock Behavior

```typescript
// ❌ BAD: Testing that the mock exists
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
});

// ✅ GOOD: Test real component
test('renders sidebar', () => {
  render(<Page />);
  expect(screen.getByRole('navigation')).toBeInTheDocument();
});
```

**Gate:** "Am I testing real behavior or just mock existence?" If mock existence → delete the assertion.

## Anti-Pattern 2: Test-Only Methods in Production

```typescript
// ❌ BAD: destroy() only used in tests
class Session {
  async destroy() {
    /* cleanup */
  }
}

// ✅ GOOD: Test utilities handle cleanup
// In test-utils/
export async function cleanupSession(session: Session) {
  /* cleanup */
}
```

**Gate:** "Is this method only used by tests?" If yes → put it in test utilities.

## Anti-Pattern 3: Mocking Without Understanding

```
BEFORE mocking any method:
  1. "What side effects does the real method have?"
  2. "Does this test depend on any of those side effects?"
  3. "Do I fully understand what this test needs?"

  IF depends on side effects → mock at lower level
  IF unsure → run with real implementation first, then add minimal mocking
```

## Anti-Pattern 4: Incomplete Mocks

Mock the COMPLETE data structure, not just fields your immediate test uses. Partial mocks fail silently when downstream code accesses omitted fields.

## Anti-Pattern 5: Tests as Afterthought

Testing is part of implementation, not a follow-up. TDD prevents this by definition.

## Quick Reference

| Anti-Pattern                    | Fix                                           |
| ------------------------------- | --------------------------------------------- |
| Assert on mock elements         | Test real component or unmock it              |
| Test-only methods in production | Move to test utilities                        |
| Mock without understanding      | Understand dependencies first, mock minimally |
| Incomplete mocks                | Mirror real API completely                    |
| Tests as afterthought           | TDD - tests first                             |
| Over-complex mocks              | Consider integration tests                    |

## Red Flags

- Assertion checks for `*-mock` test IDs
- Methods only called in test files
- Mock setup is >50% of test
- Can't explain why mock is needed
