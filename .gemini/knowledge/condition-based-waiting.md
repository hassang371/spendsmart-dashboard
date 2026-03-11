# Condition-Based Waiting

**Load this when:** tests use `setTimeout`/`sleep`, tests are flaky, or waiting for async operations.

## Core Principle

Wait for the **actual condition** you care about, not a guess about how long it takes.

```typescript
// ❌ BEFORE: Guessing at timing
await new Promise((r) => setTimeout(r, 50));
const result = getResult();

// ✅ AFTER: Waiting for condition
await waitFor(() => getResult() !== undefined);
const result = getResult();
```

## Quick Patterns

| Scenario       | Pattern                                              |
| -------------- | ---------------------------------------------------- |
| Wait for event | `waitFor(() => events.find(e => e.type === 'DONE'))` |
| Wait for state | `waitFor(() => machine.state === 'ready')`           |
| Wait for count | `waitFor(() => items.length >= 5)`                   |
| Wait for file  | `waitFor(() => fs.existsSync(path))`                 |

## Generic Implementation

```typescript
async function waitFor<T>(
  condition: () => T | undefined | null | false,
  description: string,
  timeoutMs = 5000,
): Promise<T> {
  const startTime = Date.now();
  while (true) {
    const result = condition();
    if (result) return result;
    if (Date.now() - startTime > timeoutMs) {
      throw new Error(
        `Timeout waiting for ${description} after ${timeoutMs}ms`,
      );
    }
    await new Promise((r) => setTimeout(r, 10)); // Poll every 10ms
  }
}
```

## Common Mistakes

- ❌ Polling too fast (`setTimeout(check, 1)`) → ✅ Poll every 10ms
- ❌ No timeout (loop forever) → ✅ Always include timeout with clear error
- ❌ Stale data (cache before loop) → ✅ Call getter inside loop for fresh data

## When Arbitrary Timeout IS Correct

Only when testing actual timing behavior (debounce, throttle). Requirements:

1. First wait for triggering condition
2. Based on known timing (not guessing)
3. Comment explaining WHY
