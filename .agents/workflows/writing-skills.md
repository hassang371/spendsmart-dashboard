---
description: how to create new skills, workflows, or skill+workflow pairs using the skill-creator toolkit
---

# Creating Skills & Workflows

## When to Use

Use when you need to create ANY new capability:

- A new workflow (single `.md` procedural guide)
- A new skill (folder with scripts, references, assets)
- A skill+workflow pair (heavy toolkit + organic trigger)
- Improving or evaluating an existing skill

## Process

1. **Read** `.agents/skills/skill-creator/SKILL.md` for the full creation framework
2. Start with **Step 0: Classification Decision** to determine the right format:
   - Needs bundled scripts/assets? → **Skill** (folder in `.agents/skills/`)
   - Pure procedure, no scripts? → **Workflow** (file in `.agents/workflows/`)
   - Both needed? → **Skill + Workflow pair**
3. Follow the skill-creator's interview → draft → test → evaluate → iterate loop
4. Use bundled tools in `.agents/skills/skill-creator/`:
   - `scripts/` — Eval runners, benchmarking, description optimizer, packaging
   - `agents/` — Grader, comparator, analyzer prompts for evaluation
   - `eval-viewer/` — HTML viewer for reviewing test results
   - `references/schemas.md` — JSON schemas for evals and grading
