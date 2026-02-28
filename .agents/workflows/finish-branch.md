---
description: how to complete development on a feature branch with merge, PR, or cleanup
---

# Finishing a Development Branch

## Overview

Guide completion of dev work: verify tests → present options → execute → clean up.

**This workflow is OPTIONAL.** Only applies when working on feature branches.

## The Process

### Step 1: Verify Tests

Run project test suite. If tests fail → stop, fix first.

### Step 2: Present Options

Present exactly these 4 options to user via `notify_user`:

1. **Merge locally** to base branch
2. **Push and create PR**
3. **Keep branch as-is** (handle later)
4. **Discard work**

### Step 3: Execute Choice

| Option     | Merge | Push | Keep Worktree | Cleanup Branch |
| ---------- | ----- | ---- | ------------- | -------------- |
| 1. Merge   | ✓     | -    | -             | ✓              |
| 2. PR      | -     | ✓    | ✓             | -              |
| 3. Keep    | -     | -    | ✓             | -              |
| 4. Discard | -     | -    | -             | ✓ (force)      |

**Option 4 requires typed "discard" confirmation** before executing.

### Step 4: Cleanup Worktree

For options 1, 2, 4: remove worktree if exists.
For option 3: keep worktree.

## Red Flags

- Proceeding with failing tests
- Merging without verifying tests on result
- Deleting work without confirmation
- Force-pushing without explicit request
