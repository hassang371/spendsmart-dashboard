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
| `documentation-gate.md` | The five documentation gates: Discovery Gate, Design Gate, Spec Review Gate, Commit Gate, and Implementation Sync Gate. Defines exactly when to create docs, when to run spec review, and when commits are allowed. Includes investigation→BUG promotion rule and bug-iteration override. |
| `skills-routing.md` | Resolution rules: how a workflow situation (e.g. "spec review") resolves to a concrete skill via `skills-registry.md`. Fallback procedure when bound skill isn't loaded. Override rules. |
| `commit-strategy.md` | Conventional commit prefixes, mandatory `Refs:` line rule, bug-iteration `wip:` rule (no `fix:` until user confirms resolved). |
| `task-tracking.md` | Protocol for using `TaskCreate`, `TaskUpdate`, and `TaskList` for all multi-step work. Defines doc taxonomy (Feature LLD / Bug / ADR / Design Doc / Plan). |
| `frontend/nextjs.md` | Next.js-specific rules auto-loaded when working on `apps/web/`. |
| `backend/fastapi.md` | FastAPI-specific rules auto-loaded when working on `apps/api/`. |

### .claude/workflow.md

Master workflow for SCALE. Auto-referenced from `CLAUDE.md` startup protocol. Pure situation
language — does not name skills directly. The 8-step pipeline: Phase 0 Investigate → Brainstorm →
Document → Plan → Execute (TDD vertical slicing) → Doc Sync → Self review → Adversarial (optional) →
Verify → Commit. Bug iteration loop with user-confirm gate is encoded as Step 6 override.

### .claude/skills-registry.md

The ONLY place skill names live. Maps each workflow situation (e.g. "spec review", "TDD execution",
"adversarial review") to the concrete skill that handles it. When plugins change, update this file —
the workflow stays stable.

### .claude/skills/

Local project skills — not the same as the plugin skills from installed marketplaces.

| File | Purpose |
|---|---|
| `design-docs/SKILL.md` | Progressive skill for writing design docs (Feature LLDs, Bug Reports, ADRs, Design Doc updates). Tells Claude Code which reference files to load and when, based on the doc type being written. |
| `website-cloner/SKILL.md` | Skill for cloning a website's visual design into the codebase. |

### .claude/settings.json

Claude Code project settings — configures which hooks run on which events (e.g. pre-tool-call validation), permission levels, and any project-specific behaviour overrides.

### .claude/settings.local.json

Local overrides to settings (gitignored). Developer-specific configuration that should not be shared.

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

Full details: `.claude/CLAUDE.md`, `.claude/workflow.md`, and `.claude/skills-registry.md`.

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-03 | Initial version created for team onboarding (Hassan + Jessica). |
