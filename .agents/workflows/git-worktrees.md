---
description: how to use git worktrees for isolated feature development
---

# Using Git Worktrees

## Overview

Git worktrees create isolated workspaces sharing the same repo. Work on multiple branches simultaneously without switching.

**This workflow is OPTIONAL.** Only use when git isolation is needed.

## When to Use

- Starting feature work that needs isolation
- Working on multiple features simultaneously
- Before executing plans in a separate branch

## Directory Selection

Follow this priority:

1. Check if `.worktrees/` or `worktrees/` exists → use it
2. Check `.gitignore` for worktree preference
3. Ask user

## Safety Verification

**For project-local directories:**

```bash
git check-ignore -q .worktrees 2>/dev/null
```

If NOT ignored: add to `.gitignore` before creating worktree.

## Creation Steps

```bash
# 1. Create worktree with new branch
git worktree add .worktrees/<branch-name> -b <branch-name>

# 2. Change to worktree directory
cd .worktrees/<branch-name>

# 3. Install dependencies (auto-detect)
# Node: npm install
# Python: pip install -r requirements.txt
# Go: go mod download

# 4. Verify clean baseline
# Run project's test suite
```

## Quick Reference

| Situation                  | Action                                 |
| -------------------------- | -------------------------------------- |
| `.worktrees/` exists       | Use it (verify ignored)                |
| Neither exists             | Ask user preference                    |
| Directory not ignored      | Add to .gitignore first                |
| Tests fail during baseline | Report failures, ask before proceeding |

## Cleanup

When done with worktree:

```bash
git worktree remove <worktree-path>
```

**Pairs with:** `finish-branch.md` for completing feature work.
