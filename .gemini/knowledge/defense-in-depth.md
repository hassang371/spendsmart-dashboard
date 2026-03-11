# Defense-in-Depth Validation

**Load this when:** fixing a bug caused by invalid data, or adding validation after a debugging session.

## Core Principle

Single validation: "We fixed the bug."
Multiple layers: "We made the bug **impossible**."

## The Four Layers

### Layer 1: Entry Point Validation

Reject obviously invalid input at API boundary.

```typescript
function createProject(name: string, workingDirectory: string) {
  if (!workingDirectory || workingDirectory.trim() === "") {
    throw new Error("workingDirectory cannot be empty");
  }
}
```

### Layer 2: Business Logic Validation

Ensure data makes sense for this specific operation.

```typescript
function initializeWorkspace(projectDir: string) {
  if (!projectDir) {
    throw new Error("projectDir required for workspace initialization");
  }
}
```

### Layer 3: Environment Guards

Prevent dangerous operations in specific contexts (e.g., tests).

```typescript
if (process.env.NODE_ENV === "test" && !path.startsWith(tmpdir())) {
  throw new Error("Refusing operation outside temp dir during tests");
}
```

### Layer 4: Debug Instrumentation

Capture context for forensics.

```typescript
logger.debug("About to git init", {
  directory,
  cwd: process.cwd(),
  stack: new Error().stack,
});
```

## Applying the Pattern

When you find a bug:

1. **Trace the data flow** — Where does the bad value originate? Where is it used?
2. **Map all checkpoints** — List every point data passes through
3. **Add validation at each layer** — Entry, business, environment, debug
4. **Test each layer** — Try to bypass layer 1, verify layer 2 catches it

## Key Insight

All four layers are necessary. Different code paths bypass entry validation. Mocks bypass business logic checks. Edge cases on different platforms need environment guards. Don't stop at one validation point.
