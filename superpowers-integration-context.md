# Superpowers + Context Engineering Integration — Complete Documentation

> This document captures every decision, file, issue, and fix made during the integration of the Superpowers and Agent Skills for Context Engineering frameworks into the Antigravity AI coding assistant. Use this as context for any future conversation about this system.

---

## 1. Project Overview

### Goal

Integrate two open-source AI skill frameworks into Antigravity so they work organically, continuously, and without explicit user invocation — while preventing Gemini model drift and artifact conflicts.

### Source Repositories

- **Superpowers** — `/Users/hassangameryt/Downloads/superpowers-main/` — A complete software development workflow for coding agents. Contains 14 skills covering brainstorming, planning, execution, TDD, verification, code review, debugging, parallel agents, git workflows, and skill creation.
- **Agent Skills for Context Engineering** — `/Users/hassangameryt/Downloads/Agent-Skills-for-Context-Engineering-main/` — A collection of context engineering skills and knowledge covering attention budgets, context degradation, compression strategies, multi-agent patterns, memory systems, tool design, and evaluation frameworks.

### Target Environment

- **Antigravity** — Google's AI coding assistant (VS Code extension)
- **Models Used** — Gemini 3.1 Pro (primary), Claude Opus 4.5 (secondary)
- **Workspace** — `/Users/hassangameryt/Documents/Antigravity/Test/`

---

## 2. Problems Identified

### Problem 1: Gemini Model Drift

Gemini models revert to native reasoning after a few prompts, ignoring any injected framework. The model would stop following TDD, skip verification, and create artifacts in the wrong locations.

### Problem 2: Artifact Path Conflicts

Superpowers' `writing-plans` skill saves to `docs/plans/*.md`. Antigravity's native system uses `implementation_plan.md`, `task.md`, and `walkthrough.md` as artifacts in `~/.gemini/antigravity/brain/<conversation-id>/`. Both systems ran simultaneously and conflicted.

### Problem 3: Framework Fighting

Explicitly telling the model "use your superpowers framework" or "use the brainstorming skill" created friction. The model would sometimes follow the skill, sometimes override it with native reasoning, and sometimes do both simultaneously.

### Problem 4: Search Tool Can't Find Hidden Directories

When the model tried to find workflow files, it used a content search tool (like grep) which doesn't index hidden directories (`.agents/`, `.gemini/`). Searches returned 0 results.

### Problem 5: Partial Workflow Compliance

Even after fixing the search issue, the model would read `verify.md` (because the task was verification) but skip `write-plan.md` before creating `task.md`. It followed the letter partially but not the spirit.

### Problem 6: No Context Persistence

There was no mechanism for the model to maintain context across long sessions or between conversations. Antigravity's built-in checkpoints are lossy and not user-editable.

---

## 3. Architecture & Design Decisions

### Core Strategy: Harmonize, Don't Override

Adapt skills to work WITH Antigravity's native system rather than fighting it. All artifact paths redirect to Antigravity's native locations.

### Three-Layer Architecture

```
Layer 1: Global Rule (Antigravity UI → Customizations → Rules → + Global)
  ├── Always-on, loaded before every conversation
  ├── Core philosophy, anti-drift, workflow triggers
  └── ~160 lines of markdown

Layer 2: Workspace Workflows (.agents/workflows/*.md)
  ├── On-demand procedural skills
  ├── Loaded only when triggered by context
  └── 16 files

Layer 3: Workspace Knowledge (.gemini/knowledge/*.md)
  ├── Reference documentation
  ├── Loaded only when topic is relevant
  └── 14 files
```

### Key Design Decisions

| Decision                                         | Rationale                                                                                 |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| **Local-first (project workspace)**              | Global installation confused the model about where to save files. Local ensures accuracy. |
| **Individual knowledge files (not condensed)**   | Better for progressive disclosure — model loads only what's relevant.                     |
| **Bootstrap script for new projects**            | Solves the "every new project needs files" problem without sacrificing accuracy.          |
| **No slash commands**                            | Workflows trigger organically based on context and the Global Rule's activation map.      |
| **Redirect all artifacts to Antigravity native** | `task.md`, `implementation_plan.md`, `walkthrough.md` — no competing files.               |
| **view_file not search**                         | Hidden directories aren't indexed by search tools. Explicit file reads work reliably.     |
| **5-turn checkpoint frequency**                  | Gemini drifts quickly; 10 turns was too loose.                                            |
| **Startup protocol**                             | Model reads `current_state.md` on first turn of every new conversation.                   |

---

## 4. Files Created — Complete Inventory

### 4.1 Global Rule (1 file)

| File             | Path                               | Purpose                                                                                                                                                                                                                    |
| ---------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `global-rule.md` | `.agents/workflows/global-rule.md` | Content to paste into Antigravity Rules UI. Contains startup protocol, core philosophy, pre-action gate, activation map, anti-drift protocol, artifact mapping, context engineering principles, context persistence rules. |

**Key Sections in Global Rule:**

1. **Startup Protocol** — On first turn, read `.gemini/current_state.md` if it exists.
2. **Core Philosophy** — TDD, YAGNI, DRY, Verification-First, Evidence Before Claims.
3. **Mandatory Pre-Action Gate** — Decision tree: "What am I about to do? → Read this workflow FIRST."
4. **How to Access Workflows** — Explicit instruction to use `view_file`, never search.
5. **Activation Map** — Table mapping 13 situations to specific workflow files.
6. **Anti-Drift Protocol** — Self-check every 3 turns with 8 red flags.
7. **Artifact Mapping** — Table mapping artifact types to Antigravity native locations.
8. **Context Engineering Principles** — 5 principles (attention budget, progressive disclosure, signal/noise, position awareness, compression triggers).
9. **Context Persistence** — Checkpoint every 5 turns to `.gemini/current_state.md`.
10. **Final Mandate** — Non-optional enforcement language.

---

### 4.2 Workflow Files (16 files)

All located in `.agents/workflows/`. Each has YAML frontmatter with `description` field for Antigravity's auto-discovery.

| #   | File                          | Source      | Purpose                                                                                                       |
| --- | ----------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------- |
| 1   | `brainstorm.md`               | Superpowers | Socratic design refinement through dialogue. Output → `implementation_plan.md` artifact.                      |
| 2   | `write-plan.md`               | Superpowers | Break work into bite-sized tasks. Output → `task.md` + `implementation_plan.md` artifacts.                    |
| 3   | `execute-plan.md`             | Superpowers | Execute plans in batches with review checkpoints. Uses `task.md` for tracking, `notify_user` for checkpoints. |
| 4   | `tdd.md`                      | Superpowers | Red-green-refactor cycle. Strong anti-rationalization language. Updates `task.md` after each cycle.           |
| 5   | `verify.md`                   | Superpowers | Evidence before claims. Run commands, read output, then claim. Output → `walkthrough.md` artifact.            |
| 6   | `request-code-review.md`      | Superpowers | Pre-review checklist. When and how to request reviews.                                                        |
| 7   | `receive-code-review.md`      | Superpowers | Responding to feedback with rigor. Verify before implementing, reasoned pushback when needed.                 |
| 8   | `systematic-debugging.md`     | Superpowers | 4-phase root cause analysis (Reproduce, Isolate, Root Cause, Fix+Verify).                                     |
| 9   | `subagent-driven-dev.md`      | Superpowers | Fresh subagent per task with 2-stage review (spec compliance, then code quality).                             |
| 10  | `dispatch-parallel-agents.md` | Superpowers | Concurrent subagent workflows for 2+ independent tasks.                                                       |
| 11  | `git-worktrees.md`            | Superpowers | Optional: Git worktrees for isolated feature development.                                                     |
| 12  | `finish-branch.md`            | Superpowers | Optional: Complete work on feature branch (merge/PR/keep/discard).                                            |
| 13  | `writing-skills.md`           | Superpowers | Meta-skill for creating new workflow skills using TDD.                                                        |
| 14  | `using-superpowers.md`        | Superpowers | Introduction and overview of the skills system.                                                               |
| 15  | `global-rule.md`              | Custom      | Reference copy of Global Rule content (for pasting into UI).                                                  |
| 16  | `context-checkpoint.md`       | Custom      | Context persistence — writes structured state to `.gemini/current_state.md`.                                  |

---

### 4.3 Knowledge Files (14 files)

All located in `.gemini/knowledge/`. These are condensed reference documents.

| #   | File                         | Source                      | Content                                                                                         |
| --- | ---------------------------- | --------------------------- | ----------------------------------------------------------------------------------------------- |
| 1   | `context-fundamentals.md`    | Context Engineering         | Attention budget, progressive disclosure, 5 key principles.                                     |
| 2   | `context-degradation.md`     | Context Engineering         | 5 degradation patterns (lost-in-middle, poisoning, distraction, confusion, clash) + mitigation. |
| 3   | `context-compression.md`     | Context Engineering         | Tokens-per-task optimization, 3 compression approaches, structured summary template.            |
| 4   | `context-optimization.md`    | Context Engineering         | 4 strategies: compaction, observation masking, KV-cache optimization, partitioning.             |
| 5   | `multi-agent-patterns.md`    | Context Engineering         | 3 architectures (supervisor, peer, hierarchical), token economics, failure modes.               |
| 6   | `memory-systems.md`          | Context Engineering         | 5 memory layers, choosing architecture, retrieval strategies, anti-patterns.                    |
| 7   | `tool-design.md`             | Context Engineering         | Consolidation principle, naming, descriptions, error context.                                   |
| 8   | `filesystem-context.md`      | Context Engineering         | Scratchpads, structured knowledge files, dynamic discovery, artifact trails.                    |
| 9   | `evaluation.md`              | Context Engineering         | Probe-based evaluation, 6 quality dimensions, LLM-as-judge.                                     |
| 10  | `project-development.md`     | Context Engineering         | Task-model fit, idempotent pipelines, development workflow.                                     |
| 11  | `testing-anti-patterns.md`   | Superpowers (supplementary) | 5 testing anti-patterns with gate functions. Extends TDD workflow.                              |
| 12  | `defense-in-depth.md`        | Superpowers (supplementary) | 4-layer validation pattern for bug prevention. Extends debugging.                               |
| 13  | `condition-based-waiting.md` | Superpowers (supplementary) | Replace sleep() with condition polling. Extends testing.                                        |
| 14  | `persuasion-principles.md`   | Superpowers (supplementary) | Research-backed psychology on skill language effectiveness.                                     |

---

### 4.4 Other Files

| File                  | Path                       | Purpose                                                                                                           |
| --------------------- | -------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `init-superpowers.sh` | Project root               | Bootstrap script — copies workflows + knowledge to new projects. Auto-detects both flat depot and project layout. |
| `current_state.md`    | `.gemini/current_state.md` | Context checkpoint — structured state for cross-conversation continuity.                                          |

---

## 5. Issues Found and Fixed (Chronological)

### Issue 1: Search Returns 0 Results

- **Symptom:** Model searched "verify.md" → 0 results. Tried 3 times.
- **Root Cause:** Model used content search (like grep) which skips hidden directories (`.agents/`).
- **Fix:** Added explicit instructions to Global Rule: "READ the file directly. Do NOT search for it. Use `view_file` on the full path."
- **Result:** Next test showed `Analyzed verify.md #L1-80` ✅

### Issue 2: Partial Workflow Compliance

- **Symptom:** Model read `verify.md` but skipped `write-plan.md` before creating `task.md`.
- **Root Cause:** Global Rule said "check workflows" but didn't specify WHICH workflow for WHICH action.
- **Fix:** Added Mandatory Pre-Action Gate with explicit decision tree:
  ```
  → Build something new? READ brainstorm.md FIRST.
  → Create a task list? READ write-plan.md FIRST.
  → Write code? READ tdd.md FIRST.
  ```
- **Result:** Model now follows the gate (verified in test).

### Issue 3: No Context Persistence

- **Symptom:** Long conversations lost critical details. No way to carry context to new conversations.
- **Fix:** Created `context-checkpoint.md` workflow. Writes structured summaries to `.gemini/current_state.md` every 5 turns.
- **Result:** State persists on disk, readable by any future conversation.

### Issue 4: Startup Protocol

- **Symptom:** New conversations started from scratch.
- **Fix:** Added startup protocol to Global Rule: "On VERY FIRST turn, check if `.gemini/current_state.md` exists. If yes, READ it."
- **Result:** Model reads past state on first turn of new conversations.

### Issue 5: Bootstrap Script Path Detection

- **Symptom:** Running `init-superpowers.sh` from a new project said "Depot must contain 'workflows/' and 'knowledge/' directories."
- **Root Cause:** Script looked for `workflows/` at root level, but actual files were in `.agents/workflows/`.
- **Fix:** Updated script to auto-detect both directory layouts (flat depot and project layout).
- **Result:** Script works from any new project root.

---

## 6. Test Results (3 Iterations)

### Test 1 (Before Fixes)

- Model searched "verify.md" → 0 results ❌
- Searched again → 0 results ❌
- Searched "workflows" → 0 results ❌
- Created Task artifact using native system (not workflow-guided)
- Global Rule identity active: "Principal Engineer" ✅

### Test 2 (After Search Fix)

- `Analyzed verify.md #L1-80` ✅
- Created Task artifact with checklist format ✅
- Used task boundaries with progress updates ✅
- Browser subagent dispatched for visual comparison ✅
- DID NOT read `write-plan.md` before creating task ⚠️

### Test 3 (After Pre-Action Gate)

- `Analyzed verify.md #L1-80` ✅
- Created Task artifact ✅
- Ran `curl` to verify both servers ✅
- Used browser subagent for visual comparison ✅
- Used scratchpad (Antigravity native feature) for intermediate notes ✅
- Global Rule fully active in Rules panel ✅

---

## 7. How It All Works Together

### New Conversation Flow

```
1. Model starts → Global Rule loaded (from Antigravity Rules UI)
2. Startup Protocol → reads .gemini/current_state.md (if exists)
3. User sends message
4. Pre-Action Gate → "What am I about to do?" → reads relevant workflow
5. Model follows workflow procedure
6. Every 3 turns → anti-drift self-check
7. Every 5 turns → context checkpoint to .gemini/current_state.md
8. Before claiming done → reads verify.md, runs verification commands
9. Results saved to walkthrough.md artifact
```

### New Project Setup

```
1. Navigate to new project root
2. Run: bash /path/to/Test/init-superpowers.sh
3. Copies 16 workflows → .agents/workflows/
4. Copies 14 knowledge files → .gemini/knowledge/
5. Global Rule already in Antigravity UI (one-time setup)
6. Done — start a new conversation
```

### Adding a New Skill

```
1. Tell the model: "Use the writing-skills.md workflow to create a skill called <name>"
2. Model creates .agents/workflows/<name>.md with proper structure
3. Add one row to Global Rule's Activation Map table
4. Re-paste Global Rule into Antigravity UI
5. Done — model will now trigger the skill organically
```

---

## 8. Directory Structure

```
/Users/hassangameryt/Documents/Antigravity/Test/
├── .agents/
│   └── workflows/
│       ├── brainstorm.md
│       ├── context-checkpoint.md
│       ├── dispatch-parallel-agents.md
│       ├── execute-plan.md
│       ├── finish-branch.md
│       ├── git-worktrees.md
│       ├── global-rule.md
│       ├── receive-code-review.md
│       ├── request-code-review.md
│       ├── subagent-driven-dev.md
│       ├── systematic-debugging.md
│       ├── tdd.md
│       ├── using-superpowers.md
│       ├── verify.md
│       ├── write-plan.md
│       └── writing-skills.md
├── .gemini/
│   ├── current_state.md
│   └── knowledge/
│       ├── condition-based-waiting.md
│       ├── context-compression.md
│       ├── context-degradation.md
│       ├── context-fundamentals.md
│       ├── context-optimization.md
│       ├── defense-in-depth.md
│       ├── evaluation.md
│       ├── filesystem-context.md
│       ├── memory-systems.md
│       ├── multi-agent-patterns.md
│       ├── persuasion-principles.md
│       ├── project-development.md
│       ├── testing-anti-patterns.md
│       └── tool-design.md
└── init-superpowers.sh
```

---

## 9. What Antigravity Does Natively (vs What We Built)

| Feature                                                                 | Antigravity Native                               | Our System                           |
| ----------------------------------------------------------------------- | ------------------------------------------------ | ------------------------------------ |
| Workflow auto-discovery                                                 | ✅ Reads `.agents/workflows/` frontmatter        | We create the files                  |
| Artifact system (`task.md`, `implementation_plan.md`, `walkthrough.md`) | ✅ Built-in                                      | We redirect all output here          |
| Conversation checkpoints                                                | ✅ Lossy, auto-generated                         | We add structured `current_state.md` |
| Conversation summaries                                                  | ✅ Lists recent conversations in system prompt   | We add precise state                 |
| Rules UI                                                                | ✅ Paste rules that persist across conversations | We paste Global Rule here            |
| Scratchpad                                                              | ✅ Native temp doc for intermediate notes        | We don't use this                    |
| `notify_user` tool                                                      | ✅ For user communication during tasks           | Workflows use this for checkpoints   |
| `task_boundary` tool                                                    | ✅ For progress tracking                         | Workflows use this                   |

---

## 10. Known Limitations

1. **Not truly infinite context.** Checkpointing helps but is not automatic infrastructure. The model must follow the workflow to checkpoint, and if it drifts hard enough, it won't checkpoint.

2. **Gemini can still drift.** The anti-drift protocol mitigates but can't prevent 100% of drift. After very long sessions (20+ turns), expect some degradation.

3. **No automatic workflow enforcement.** The model is told to follow workflows, but there's no runtime enforcement. It's guidance, not guardrails.

4. **Knowledge files are static.** They don't auto-update. If context engineering research evolves, the files need manual updates.

5. **Bootstrap creates copies, not symlinks.** Changes to the source project don't propagate to bootstrapped projects. Re-run the script to update.

---

## 11. Future Enhancement Ideas

1. **Custom skills** — User can create project-specific skills (e.g., `system-design.md`) using the `writing-skills.md` meta-workflow.

2. **Knowledge retrieval automation** — Add a rule that forces the model to search `.gemini/knowledge/` when it encounters unfamiliar problems.

3. **Project standards file** — A `.gemini/project_standards.md` for permanent rules ("always use spaces", "always use Axios") that survive beyond `current_state.md`.

4. **Symlink-based bootstrap** — Instead of copying files, symlink to a single source for auto-updating across projects.
