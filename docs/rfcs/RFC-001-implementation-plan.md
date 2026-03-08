# CLAUDE.md Rewrite + Design-Docs Skill Update — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rewrite `.claude/CLAUDE.md` as a thin master, create modular rules in `.claude/rules/`, migrate `docs-driven-dev` workflow, and restore missing files to the design-docs skill.

**Architecture:** Master CLAUDE.md (~100-150 lines) + modular rules (global + path-scoped) + on-demand workflow + progressive-disclosure design-docs skill.

**Tech Stack:** Markdown, shell scripts, Python utilities (existing)

---

### Task 1: Restore missing files to design-docs skill

**Files:**
- Copy: `/tmp/design-doc-mermaid/references/guides/troubleshooting.md` → `.claude/skills/design-docs/references/troubleshooting.md`
- Copy: `/tmp/design-doc-mermaid/references/guides/resilient-workflow.md` → `.claude/skills/design-docs/references/resilient-workflow.md`
- Copy: `/tmp/design-doc-mermaid/scripts/resilient_diagram.py` → `.claude/skills/design-docs/scripts/resilient_diagram.py`
- Copy: `/tmp/design-doc-mermaid/scripts/mermaid_to_image.py` → `.claude/skills/design-docs/scripts/mermaid_to_image.py`

**Step 1:** Copy all 4 files

```bash
cp /tmp/design-doc-mermaid/references/guides/troubleshooting.md ".claude/skills/design-docs/references/troubleshooting.md"
cp /tmp/design-doc-mermaid/references/guides/resilient-workflow.md ".claude/skills/design-docs/references/resilient-workflow.md"
cp /tmp/design-doc-mermaid/scripts/resilient_diagram.py ".claude/skills/design-docs/scripts/resilient_diagram.py"
cp /tmp/design-doc-mermaid/scripts/mermaid_to_image.py ".claude/skills/design-docs/scripts/mermaid_to_image.py"
```

**Step 2:** Verify files exist

```bash
ls -la .claude/skills/design-docs/references/troubleshooting.md
ls -la .claude/skills/design-docs/references/resilient-workflow.md
ls -la .claude/skills/design-docs/scripts/resilient_diagram.py
ls -la .claude/skills/design-docs/scripts/mermaid_to_image.py
```

**Step 3:** Commit

```bash
git add .claude/skills/design-docs/
git commit -m "feat(skills): restore missing files to design-docs from upstream"
```

---

### Task 2: Rewrite design-docs SKILL.md with progressive disclosure

**Files:**
- Modify: `.claude/skills/design-docs/SKILL.md`

**Step 1:** Rewrite SKILL.md merging original's decision tree with SCALE's doc workflow. Must include:
- Progressive disclosure decision tree (routes to specific guides on demand)
- Doc type detection (feature → LLD, bug → bug report, RFC → RFC, HLD sync)
- SCALE-specific process (auto-numbering, HLD sync check, commit docs before code)
- Reference table mapping situations to specific files
- ~200 lines max

**Step 2:** Verify the file reads correctly

```bash
wc -l .claude/skills/design-docs/SKILL.md
# Expected: ~150-200 lines
```

**Step 3:** Commit

```bash
git add .claude/skills/design-docs/SKILL.md
git commit -m "feat(skills): rewrite design-docs SKILL.md with progressive disclosure"
```

---

### Task 3: Create `.claude/workflows/docs-driven-dev.md`

**Files:**
- Create: `.claude/workflows/docs-driven-dev.md`

**Step 1:** Create the directory and file. Claude-native version of the master workflow:
- Step 1: Brainstorm → `superpowers:brainstorming` (no round limit)
- Step 2: Document → Read `.claude/skills/design-docs/` (LLD/HLD/bug/RFC)
- Step 3: Plan → `superpowers:writing-plans`
- Step 4: Execute → `superpowers:test-driven-development` + `superpowers:executing-plans`
- Step 5: Verify → `superpowers:verification-before-completion`
- Step 6: Commit → conventional commits, HLD sync check
- All artifact references use Claude Code native tools (TaskCreate, not task.md)
- ~80-100 lines

**Step 2:** Verify

```bash
wc -l .claude/workflows/docs-driven-dev.md
```

**Step 3:** Commit

```bash
git add .claude/workflows/
git commit -m "feat(workflows): create Claude-native docs-driven-dev workflow"
```

---

### Task 4: Create `.claude/rules/` files

**Files:**
- Create: `.claude/rules/superpowers.md` (~60 lines)
- Create: `.claude/rules/design-docs.md` (~10 lines)
- Create: `.claude/rules/task-tracking.md` (~20 lines)
- Create: `.claude/rules/commit-strategy.md` (~20 lines)

**Step 1:** Create `rules/superpowers.md` — skill table, brainstorming gate, anti-drift protocol

**Step 2:** Create `rules/design-docs.md` — thin trigger for design-docs skill

**Step 3:** Create `rules/task-tracking.md` — Claude native task tools, artifact mapping

**Step 4:** Create `rules/commit-strategy.md` — conventional commits, when to commit

**Step 5:** Verify all files exist and total line count

```bash
wc -l .claude/rules/*.md
# Expected: ~110 lines total
```

**Step 6:** Commit

```bash
git add .claude/rules/
git commit -m "feat(rules): create modular rules for superpowers, tasks, commits, design-docs"
```

---

### Task 5: Create path-scoped rules

**Files:**
- Create: `.claude/rules/frontend/nextjs.md` (paths: `apps/web/**/*.{ts,tsx}`)
- Create: `.claude/rules/backend/fastapi.md` (paths: `apps/api/**/*.py`, `apps/worker/**/*.py`, `packages/**/*.py`)

**Step 1:** Create `rules/frontend/nextjs.md` — SCALE-specific Next.js conventions (Supabase SSR, component organization, app/ structure)

**Step 2:** Create `rules/backend/fastapi.md` — SCALE-specific FastAPI conventions (domain module structure, Celery patterns, Supabase client)

**Step 3:** Verify

```bash
wc -l .claude/rules/frontend/nextjs.md .claude/rules/backend/fastapi.md
```

**Step 4:** Commit

```bash
git add .claude/rules/frontend/ .claude/rules/backend/
git commit -m "feat(rules): add path-scoped rules for Next.js and FastAPI"
```

---

### Task 6: Rewrite `.claude/CLAUDE.md`

**Files:**
- Modify: `.claude/CLAUDE.md`

**Step 1:** Rewrite CLAUDE.md as thin master (~100-150 lines):
- Identity (Principal Engineer on SCALE)
- Startup Protocol (memory + TaskList + conversation type detection)
- Tech Stack
- Dev Commands
- Project Structure
- Core Principles (TDD, verification-first, evidence, YAGNI, DRY)
- Final Mandate
- NO skill table (moved to rules/superpowers.md)
- NO task tracking rules (moved to rules/task-tracking.md)
- NO artifact mapping (moved to rules/task-tracking.md)
- NO anti-drift (moved to rules/superpowers.md)

**Step 2:** Verify line count

```bash
wc -l .claude/CLAUDE.md
# Expected: ~100-150 lines
```

**Step 3:** Commit

```bash
git add .claude/CLAUDE.md
git commit -m "feat: rewrite CLAUDE.md as thin master with modular rules"
```

---

### Task 7: Create starter MEMORY.md

**Files:**
- Create: `~/.claude/projects/-Users-hassangameryt-Documents-Antigravity-SCALE-APP/memory/MEMORY.md`

**Step 1:** Seed with key decisions from this brainstorm session:
- Installed plugins list
- Skill mapping conventions
- Artifact conventions
- File structure decisions

**Step 2:** Verify

```bash
cat ~/.claude/projects/-Users-hassangameryt-Documents-Antigravity-SCALE-APP/memory/MEMORY.md
```

**Step 3:** No git commit (memory is local, not in repo)

---

### Task 8: Final verification

**Step 1:** Verify complete file tree

```bash
find .claude/ -name "*.md" -o -name "*.py" -o -name "*.sh" | sort
```

**Step 2:** Verify CLAUDE.md is under 200 lines

```bash
wc -l .claude/CLAUDE.md
```

**Step 3:** Verify total always-loaded context (CLAUDE.md + global rules)

```bash
wc -l .claude/CLAUDE.md .claude/rules/superpowers.md .claude/rules/design-docs.md .claude/rules/task-tracking.md .claude/rules/commit-strategy.md
```

Expected: ~210 lines total always-loaded.

**Step 4:** Final commit if any stragglers

```bash
git status
```

---

### Addendum: Unplanned Changes (discovered during implementation)

The following changes were made during implementation that were not in the original plan:

| Change | Reason |
|---|---|
| Fixed `.gitignore` — removed `.claude/`, anchored `references/` and `misc/` to root | `.claude/` was gitignored, blocking all skill/rule tracking. `references/` was matching subdirectories inside `.claude/skills/` |
| Created `.claude/settings.json` | Needed to document plugin inventory and flag `fullstack-dev-skills` as disabled |
| Added `.claude/settings.local.json` to `.gitignore` | Local-only plugin overrides should not be committed |

---

> **Final status:** Implemented (2026-03-08). All 8 tasks completed in commit `cd63a8e`.
