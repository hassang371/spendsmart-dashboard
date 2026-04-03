# SCALE — AI Development Tooling Guide

> **Doc ID:** ai-tooling-guide
> **Last Updated:** 2026-04-03
> **Status:** Current
> **Version:** 1.0
> **DRI:** Hassan

## Overview

SCALE is developed with AI coding assistants — primarily **Claude Code** (Anthropic) and optionally **Gemini CLI** (Google). This document explains every hidden directory that supports AI-assisted development, what each file does, and how the overall workflow hangs together. If you are new to the team and will be using Claude Code, read this before writing any code.

---

## Why AI Tooling Matters Here

The AI assistants on this project are not just autocomplete. They follow a structured workflow with enforced gates: brainstorming before code, design docs before implementation, tests before logic, and a `Refs:` line on every `fix:` and `feat:` commit. The hidden directories below are what make that possible — they are the configuration that turns a generic AI assistant into a principal engineer who knows this codebase.

---

## .claude/ — Claude Code Configuration

Claude Code is the primary AI assistant. This directory configures how it behaves on the SCALE project.

### .claude/CLAUDE.md

The top-level prompt for Claude Code. Loaded automatically at the start of every session. Defines:
- Role (Principal Engineer on SCALE)
- Startup protocol (run `TaskList`, evaluate request, route to the right workflow)
- Tech stack summary
- Dev commands quick reference
- Project structure overview
- Core principles (TDD, Verification-First, YAGNI, DRY)
- Final mandate (no exceptions to workflow gates)

**Read this first** if you are setting up Claude Code on this project.

### .claude/rules/

Rules are **auto-loaded by Claude Code on every session**. They enforce the non-negotiable constraints of the development workflow.

| File | Purpose |
|---|---|
| `superpowers.md` | Master workflow routing table. Defines the Discovery Gate (defect found → bug report before discussing solutions), the Brainstorming Gate (brainstorm before any non-trivial code change), and the full skill table mapping situations to the correct tool or workflow. |
| `documentation-gate.md` | The five documentation gates: Discovery Gate, Design Gate, Spec Review Gate, Commit Gate, and Implementation Sync Gate. Defines exactly when to create docs, when to run spec review, and when commits are allowed. |
| `commit-strategy.md` | Conventional commit prefixes, when to commit, and the mandatory `Refs:` line rule — every `fix:` commit must reference a `docs/bugs/BUG-NNN` file, every `feat:` commit must reference a `docs/features/NNN` file. |
| `task-tracking.md` | Protocol for using `TaskCreate`, `TaskUpdate`, and `TaskList` for all multi-step work. Defines that project docs live in `docs/` and that `task.md` files are never created. |
| `frontend/nextjs.md` | Next.js-specific rules auto-loaded when working on `apps/web/`. |
| `backend/fastapi.md` | FastAPI-specific rules auto-loaded when working on `apps/api/`. |

### .claude/workflows/

Workflow files are **not auto-loaded**. Claude Code reads them explicitly when the relevant workflow is needed. They contain the detailed step-by-step procedures.

| File | Purpose |
|---|---|
| `docs-driven-dev.md` | The master development workflow for SCALE. Covers every step from idea to verified commit: brainstorm → LLD → spec review → user approval → TDD → implementation → deviation log → verification → commit with `Refs:`. |

### .claude/skills/

Local project skills — not the same as the global plugin skills from `.claude/plugins/`.

| File | Purpose |
|---|---|
| `design-docs/SKILL.md` | Progressive skill for writing design docs (Feature LLDs, Bug Reports, RFCs, HLDs). Tells Claude Code which reference files to load and when, based on the doc type being written. |
| `website-cloner/SKILL.md` | Skill for cloning a website's visual design into the codebase. |

### .claude/settings.json

Claude Code project settings — configures which hooks run on which events (e.g. pre-tool-call validation), permission levels, and any project-specific behaviour overrides.

### .claude/settings.local.json

Local overrides to settings (gitignored). Developer-specific configuration that should not be shared.

---

## .agents/ — Shared Agent Skills

Skills and workflows that are shared across multiple agent types (Claude Code, Gemini, others). These mirror the Claude-specific `.claude/` directory but are not tied to any single AI assistant.

### .agents/skills/

Each subdirectory is a named skill with a `SKILL.md` entry point.

| Skill | Purpose |
|---|---|
| `design-docs/` | Writing design docs (same goal as `.claude/skills/design-docs/`, shared version). |
| `tdd/` | Test-driven development — red → green → refactor cycle. |
| `systematic-debugging/` | Structured debugging process: reproduce → isolate → hypothesise → verify → fix. |
| `subagent-driven-dev/` | Pattern for breaking work into parallel subagent tasks. |
| `request-code-review/` | How to dispatch and frame a code review request. |
| `fullstack-guardian/` | Full-stack feature development skill. |
| `secure-code-guardian/` | Security-focused code review and implementation. |
| `typescript-pro/` | TypeScript best practices for this codebase. |
| `nextjs-developer/` | Next.js App Router patterns and SCALE conventions. |
| `python-pro/` | Python best practices and SCALE API patterns. |
| `react-expert/` | React component patterns. |
| `feature-forge/` | Structured requirements gathering for new features. |
| `skill-creator/` | Skill for creating new skills. |
| `webapp-testing/` | Web app testing strategies. |
| `mcp-builder/` | Building MCP (Model Context Protocol) servers. |
| `monitoring-expert/` | Setting up monitoring and observability. |
| `sre-engineer/` | SRE practices, SLO definition. |
| `devops-engineer/` | Docker, CI/CD, infra configuration. |
| `evaluation/` | Evaluating ML model quality. |
| `test-master/` | Writing and structuring test suites. |
| `microservices-architect/` | Architecture patterns (informational for future reference). |
| `database-optimizer/` | Database query and schema optimisation. |
| `context-*` | Context management skills for long AI sessions (compression, fundamentals, optimisation). |

### .agents/workflows/

Cross-agent workflow reference files — the same procedures as `.claude/workflows/` but in a format readable by any agent.

| File | Purpose |
|---|---|
| `docs-driven-dev.md` | Master development workflow (cross-agent version). |
| `brainstorm.md` | Brainstorming procedure. |
| `tdd.md` | TDD procedure. |
| `systematic-debugging.md` | Debugging procedure. |
| `commit-strategy.md` | Commit conventions. |
| `spec-review.md` | Spec review procedure. |
| `subagent-driven-dev.md` | Parallel subagent pattern. |
| `verify.md` | Verification before claiming done. |
| `write-plan.md` | Writing an implementation plan. |
| `execute-plan.md` | Executing an existing plan. |
| `finish-branch.md` | Branch completion checklist. |
| `git-worktrees.md` | Using git worktrees for branch isolation. |
| `dispatch-parallel-agents.md` | Dispatching parallel agent tasks. |
| `request-code-review.md` | Requesting a code review. |
| `receive-code-review.md` | Handling incoming code review feedback. |
| `documentation-gates.md` | Documentation gate rules. |
| `context-checkpoint.md` | Saving context at session boundaries. |
| `skills-guide.md` | How to discover and use skills. |
| `using-superpowers.md` | Superpowers plugin introduction. |
| `writing-skills.md` | Creating new skills. |
| `global-rule.md` | Global rules applied to all workflows. |
| `ci-cd.md` | CI/CD workflow reference. |
| `k8s-troubleshooter.md` | Kubernetes troubleshooting (future reference). |
| `monitoring-expert.md` | Monitoring setup reference. |

---

## .gemini/ — Gemini CLI Context

Gemini CLI configuration for developers who prefer it over Claude Code. It mirrors the intent of `.claude/` but uses Gemini's native file format.

| File | Purpose |
|---|---|
| `context-rules.md` | Gemini session rules — equivalent to `.claude/CLAUDE.md` for Gemini. Defines the same workflow gates and principles. |
| `tech-stack.md` | Stack reference loaded at session start so Gemini knows the project's technologies. |
| `current_state.md` | Session state file — Gemini writes its current task state here for persistence across context resets. |

### .gemini/knowledge/

Domain knowledge files loaded by Gemini on demand. Each covers a topic that helps the AI reason correctly about complex areas.

| File | Purpose |
|---|---|
| `context-compression.md` | How to compress context without losing signal. |
| `context-degradation.md` | How to detect and recover from context degradation. |
| `context-fundamentals.md` | Core principles of effective AI context management. |
| `context-optimization.md` | Techniques for optimising AI session context. |
| `condition-based-waiting.md` | Pattern for waiting for conditions before proceeding (vs. polling loops). |
| `defense-in-depth.md` | Security layering principles. |
| `evaluation.md` | How to evaluate ML model outputs. |
| `filesystem-context.md` | How to use the filesystem as persistent context. |
| `memory-systems.md` | AI memory system patterns. |
| `multi-agent-patterns.md` | Patterns for coordinating multiple AI agents. |
| `persuasion-principles.md` | Principles for framing AI prompts effectively. |
| `project-development.md` | Project development workflow knowledge. |
| `testing-anti-patterns.md` | Common testing mistakes and how to avoid them. |
| `tool-design.md` | How to design good AI tool interfaces. |

---

## .github/ — CI/CD

GitHub Actions workflows that run on every push and pull request.

### .github/workflows/

| File | Trigger | Purpose |
|---|---|---|
| `ci.yml` | Push / PR to `main` | Full CI pipeline: ESLint, TypeScript check, Ruff lint, pytest (all apps + packages), Vitest (frontend), Bandit security scan, check-refs validation. Blocks merge if any step fails. |
| `deploy.yml` | Push to `main` (after CI passes) | Deploys the Docker image to Railway (backend + worker) and triggers a Vercel production deployment (frontend). Uses cosign to sign the Docker image. |
| `build-base.yml` | Manual / scheduled | Builds the Docker base image layer and pushes to GHCR. Separates the slow dependency install step from the fast app build. |
| `performance.yml` | PR to `main` | Runs performance regression tests — measures API response times against a baseline. |
| `secret-scan.yml` | Push / PR | Scans all changed files for accidentally committed secrets (API keys, passwords, tokens). |

### .github/dependabot.yml

Dependabot configuration — automatically opens PRs for outdated npm and Python dependencies on a weekly schedule.

---

## The Development Workflow (brief)

When working with Claude Code on SCALE, every non-trivial task follows this sequence:

1. **Brainstorm** — Claude invokes the brainstorming skill, asks clarifying questions, proposes approaches.
2. **Design doc** — A Feature LLD or Bug Report is written to `docs/features/` or `docs/bugs/` before any code.
3. **Spec review** — The design doc is reviewed and fixed before committing.
4. **User approval** — The committed doc is reviewed by the team.
5. **TDD** — A failing test is written first. Then the implementation makes it pass.
6. **Verification** — `make check` (lint + tsc + pytest) runs and passes. Output is read, not assumed.
7. **Commit** — `feat:` or `fix:` commit with a `Refs:` line pointing to the design doc.

Full details: `.claude/CLAUDE.md` and `.claude/workflows/docs-driven-dev.md`.

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-03 | Initial version created for team onboarding (Hassan + Jessica). |
