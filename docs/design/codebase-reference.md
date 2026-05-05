# SCALE — Codebase Reference

> **Doc ID:** codebase-reference
> **Last Updated:** 2026-04-03
> **Status:** Current
> **Version:** 1.0
> **DRI:** Hassan

## Overview

This document is the authoritative reference for every file and directory in the SCALE repository. Read it top-down for a full orientation, or jump to a section by layer. For AI development tooling (`.claude/`, `.gemini/`, `.github/`), see [`ai-tooling-guide.md`](ai-tooling-guide.md).

---

## How to Use This Doc

- **New to the codebase?** Read Overview → Repository Root → the layer(s) you own.
- **ML/AI engineer?** Go directly to [packages/](#packages--shared-mlai-libraries).
- **Full-stack?** Read [apps/api/](#appsapi--fastapi-backend) and [apps/web/](#appsweb--nextjs-frontend).
- **Need to understand infra?** See [docker-compose.yml](#repository-root), [supabase/](#supabase--database), and [.github/](#hidden-and-tooling-directories-summarised).

---

## Repository Root

These files live at the top level of the repo.

| File | Purpose |
|---|---|
| `Makefile` | All dev commands: `make dev`, `make test`, `make check`, `make install`, etc. The single source of truth for how to run things. |
| `docker-compose.yml` | Defines four Docker services: `redis` (queue/cache), `api` (FastAPI), `worker` (Celery), and `flower` (Celery monitoring UI, optional profile). |
| `Dockerfile` | Multi-stage Docker build with targets: `api`, `worker`, and `flower`. Used by docker-compose and Railway CI/CD. |
| `pyproject.toml` | Python project metadata, pytest configuration (test paths, import mode, markers), Ruff linter rules, and Bandit security scan config. |
| `requirements.txt` | All Python runtime and dev dependencies. Install via `make install` or `.venv/bin/pip install -r requirements.txt`. |
| `railway.toml` | Railway deployment configuration for the backend service. |
| `vercel.json` | Vercel deployment configuration for the Next.js frontend. |
| `.env.example` | Template for all environment variables. Copy to `.env` and fill in values. **Never commit `.env`.** |
| `.env` | Active environment variables (gitignored). Holds Supabase keys, Redis URL, CORS origins, log level, HuggingFace offline flag, Sentry DSN, Flower credentials. |
| `.env.local` | Alternative local env file (gitignored). |
| `.gitignore` | Excludes `.venv/`, `.env`, `.next/`, `__pycache__/`, `.coverage`, model files, logs, etc. |
| `.dockerignore` | Excludes files from Docker build context (mirrors `.gitignore` for Docker). |
| `.commitlintrc.json` | Commitlint config — enforces conventional commit format (`feat:`, `fix:`, `docs:`, etc.) via the git `commit-msg` hook. |
| `.markdownlint.yaml` | Markdown linting rules — applied by the pre-commit hook to all `.md` files. |
| `.pre-commit-config.yaml` | Pre-commit hook configuration. Runs commitlint (`commit-msg`) and markdown linting before each commit. |
| `.backend.log` | Backend stdout/stderr captured by `make dev` (gitignored, auto-created). |
| `.frontend.log` | Frontend stdout/stderr captured by `make dev` (gitignored, auto-created). |
| `.coverage` | Python test coverage data file (gitignored, auto-created by pytest). |

---

## apps/ — Application Layer

### apps/api/ — FastAPI Backend

The backend is a **domain-driven modular monolith**. Each domain owns its own `router.py`, `service.py`, `schemas.py`, and `tests/`. The core layer provides cross-cutting concerns.

#### apps/api/main.py

FastAPI application entry point. Registers all domain routers, attaches core middleware (CORS, security headers, rate limiting, logging), and mounts the `/api/v1` prefix.

#### apps/api/celery_app.py

Creates and configures the Celery application instance. Sets the Redis broker URL and result backend. Imported by both the API (to dispatch tasks) and the worker (to execute them).

#### apps/api/supabase_client.py

Creates the Supabase client singleton (service-role client for server-side operations). Imported wherever direct database access is needed.

#### apps/api/core/

Cross-cutting concerns shared by all domains.

| File | Purpose |
|---|---|
| `auth.py` | JWT validation via Supabase. Provides the `get_current_user` FastAPI dependency — extracts and verifies the bearer token, returns the user ID. |
| `config.py` | Pydantic `Settings` class — reads all environment variables from `.env` and exposes them as typed attributes. |
| `errors.py` | Custom exception classes (`NotFoundError`, `ValidationError`, `AuthError`, etc.) and a global exception handler that maps them to RFC 7807 Problem Detail responses. |
| `filtering.py` | Reusable query filtering helpers for date ranges, category filters, and pagination applied consistently across domain service layers. |
| `idempotency.py` | Redis-backed idempotency key checks for write endpoints — prevents duplicate ingestion on retry. |
| `logging_config.py` | Structured JSON logging configuration. Sets log level from `LOG_LEVEL` env var. Attaches request ID to every log line. |
| `pagination.py` | `PaginationParams` dependency and `PagedResponse` wrapper used by list endpoints. |
| `problem_detail.py` | RFC 7807 Problem Detail response schema and builder. |
| `rate_limiter.py` | Redis-backed sliding-window rate limiter. Applied as FastAPI middleware. Configurable per-route limits. |
| `security_headers.py` | Middleware that adds `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`, and `Referrer-Policy` headers to every response. |

#### apps/api/domains/

Each domain follows the same three-file pattern: `router.py` (HTTP layer) → `service.py` (business logic) → `schemas.py` (Pydantic models). Tests live in `tests/` alongside the domain code.

**accounts/**

Manages bank account records and per-user metadata.

| File | Purpose |
|---|---|
| `router.py` | Endpoints: list accounts, get account detail, update account name. |
| `service.py` | Reads/writes `bank_accounts` table. Handles the uncategorised transaction count used by the review badge. |
| `schemas.py` | `BankAccount`, `AccountDetail`, `AccountUpdateRequest` Pydantic models. |
| `tests/test_accounts.py` | Account CRUD endpoint tests. |
| `tests/test_merchant_batch.py` | Tests for merchant batch resolution logic. |
| `tests/test_uncategorized.py` | Tests for the uncategorised-transaction count endpoint. |

**aggregator/**

Integrates with external bank data providers (Setu Account Aggregator and manual CSV import).

| File | Purpose |
|---|---|
| `provider.py` | Abstract `AggregatorProvider` base class and `get_provider()` factory — selects `SetuProvider` or `ManualProvider` based on config. |
| `providers/setu.py` | Setu AA integration: creates consent requests, polls for consent status, fetches account statements via the Setu v2 API. Handles CORS redirect flows and webhook callbacks. |
| `providers/manual.py` | Manual import provider: accepts raw transaction JSON payloads from the frontend CSV/Excel parser. |
| `router.py` | Endpoints: initiate consent, callback webhook, list consents, fetch statement, manual import. |
| `service.py` | Orchestrates provider calls, persists raw statement data, triggers the ingestion pipeline. |
| `schemas.py` | Consent, statement, and import request/response models. |

**anomaly/**

Detects unusual spending patterns.

| File | Purpose |
|---|---|
| `router.py` | `GET /anomalies` — returns flagged transactions for the current user. |
| `service.py` | Applies statistical z-score and IQR-based detection over per-category spend. Returns transactions that exceed the threshold. |
| `schemas.py` | `AnomalyResult` model. |

**categorization/**

Classifies transactions and collects user feedback to improve the per-user model.

| File | Purpose |
|---|---|
| `router.py` | `POST /classify` (single), `POST /classify/batch`, `POST /feedback` (correction). |
| `service.py` | Calls `packages/categorization/classifier.py`, reads and writes the `transactions` table, triggers fine-tuning when enough feedback accumulates. |
| `schemas.py` | `ClassifyRequest`, `ClassifyResponse`, `FeedbackRequest` models. |

**forecasting/**

Predicts future cash flow and computes the "safe to spend" figure.

| File | Purpose |
|---|---|
| `router.py` | `GET /forecast` — returns predicted spend/income for the next N days. `GET /safe-to-spend` — returns the amount safe to spend today. |
| `service.py` | Calls `packages/forecasting/inference.py` to run the TFT model. Falls back to a simple moving average when insufficient history exists. |
| `schemas.py` | `ForecastPoint`, `ForecastResponse`, `SafeToSpendResponse` models. |

**ingestion/**

Parses, deduplicates, and stores transactions from any source.

| File | Purpose |
|---|---|
| `router.py` | `POST /ingest` — accepts a batch of raw transactions and runs the full ingestion pipeline. |
| `service.py` | Fingerprints transactions (dedup), runs categorisation, persists to `transactions` table, updates `bank_accounts`. |
| `schemas.py` | `IngestRequest`, `TransactionIn`, `IngestResponse` models. |

**training/**

Manages the lifecycle of per-user model fine-tuning jobs.

| File | Purpose |
|---|---|
| `router.py` | `POST /training/jobs` (trigger), `GET /training/jobs/{id}` (status), `GET /training/jobs` (history). |
| `service.py` | Creates a `training_jobs` record, dispatches `training_tasks.train_user_model` Celery task, polls and updates job status. |
| `schemas.py` | `TrainingJob`, `TrainingJobStatus`, `TrainingJobResponse` models. |

#### apps/api/routers/

| File | Purpose |
|---|---|
| `health.py` | `GET /api/v1/health` — returns `{"status": "ok"}`. Used by Docker healthchecks and uptime monitors. |

#### apps/api/tasks/

Celery task definitions executed by the worker.

| File | Purpose |
|---|---|
| `training_tasks.py` | `train_user_model` task — loads user feedback, fine-tunes the MiniLM adapter via Modal or local compute, uploads the adapter to Supabase Storage, writes `user_model_metadata`. |
| `cleanup_tasks.py` | Periodic cleanup tasks — removes expired consent records, purges stale training job entries. |

#### apps/api/tests/

Top-level API integration tests (not domain-specific).

| File | Purpose |
|---|---|
| `test_health.py` | Basic health endpoint smoke test. |
| `test_api_payload_construction.py` | Tests for Setu API payload construction helpers. |
| `test_feedback_updates_transactions.py` | End-to-end test: feedback → transaction category update flow. |
| `test_finetuning_bg.py` | Tests that the fine-tuning Celery task is dispatched correctly on feedback. |
| `test_training_jobs_constraint.py` | Tests the one-active-job-per-user DB constraint. |

---

### apps/web/ — Next.js Frontend

The frontend is a Next.js 16 App Router application deployed to Vercel. All pages under `/dashboard` require authentication.

#### apps/web/app/ — Route Tree

| Route | File | Purpose |
|---|---|---|
| `/` | `page.tsx` | Landing page (Webflow-imported HTML + custom CSS). |
| `/login` | `login/page.tsx` | Login form — Supabase email/password + Google OAuth. |
| `/signup` | `signup/page.tsx` | Sign-up form. |
| `/auth/callback` | `auth/callback/route.ts` | OAuth callback handler — exchanges code for session, redirects to dashboard. |
| `/auth/update-password` | `auth/update-password/page.tsx` | Password reset form. |
| `/dashboard` | `dashboard/page.tsx` | Main dashboard — Safe to Spend card, Training Job card, recent transactions. |
| `/dashboard/transactions` | `dashboard/transactions/page.tsx` | Full transaction list with filtering, category correction, and review badge. |
| `/dashboard/accounts` | `dashboard/accounts/page.tsx` | Bank account list and Setu AA connection flow. |
| `/dashboard/analytics` | `dashboard/analytics/page.tsx` | Analytics dashboard — KPI strip, category charts, spending heatmap, subscription radar, merchant rankings. |
| `/dashboard/insights` | `dashboard/insights/page.tsx` | AI-generated insights (forecast, anomalies). |
| `/dashboard/settings` | `dashboard/settings/page.tsx` | User settings — profile, preferences. |
| `layout.tsx` (root) | `app/layout.tsx` | Root layout — fonts, ThemeProvider, Sentry initialisation. |
| `layout.tsx` (dashboard) | `dashboard/layout.tsx` | Dashboard shell — sidebar navigation, auth guard. |
| `template.tsx` | `app/template.tsx` | Page transition wrapper (Framer Motion). |
| `error.tsx` | `app/error.tsx` | Route-level error boundary. |
| `global-error.tsx` | `app/global-error.tsx` | Top-level error boundary (catches errors outside layout). |
| `globals.css` | `app/globals.css` | Global CSS — Tailwind base + custom design tokens. |
| `webflow-landing.css` | `app/webflow-landing.css` | CSS imported from the Webflow landing page export. |
| `webflow-overrides.css` | `app/webflow-overrides.css` | Overrides on top of Webflow CSS to align with the app's design system. |
| `icon.svg` | `app/icon.svg` | Favicon. |
| `/api/sentry-example-api` | `app/api/sentry-example-api/route.ts` | Sentry test endpoint (development only). |
| `/sentry-example-page` | `app/sentry-example-page/page.tsx` | Sentry test page (development only). |

#### apps/web/components/

| Path | Purpose |
|---|---|
| `accounts/AccountBadge.tsx` | Displays a coloured badge for a connected bank account. |
| `accounts/AccountSwitcher.tsx` | Dropdown to switch between multiple linked bank accounts. |
| `accounts/SyncStatusIndicator.tsx` | Shows the live sync/fetch status of an account (idle, syncing, error). |
| `dashboard/SafeToSpendCard.tsx` | Displays the "safe to spend today" figure from the forecasting API. |
| `dashboard/TrainingJobCard.tsx` | Shows the current fine-tuning job status (queued, running, complete, failed). |
| `ui/ExpandableCard.tsx` | Generic expandable card shell used across the analytics dashboard. |
| `theme-provider.tsx` | Wraps the app with `next-themes` for dark/light mode support. |
| `landing-old/` | Legacy landing page components (Webflow replaced these — kept for reference, not rendered). |

#### apps/web/lib/

| File | Purpose |
|---|---|
| `privacy.ts` | PII scrubbing utilities — strips sensitive fields before sending data to Sentry or analytics. |
| `privacy.test.ts` | Unit tests for privacy scrubbing. |
| `asset-map.ts` | Maps logical asset names to hashed build-time URLs (used by the landing page image pipeline). |
| `webflow-html.ts` | Server-side utility that reads and post-processes the Webflow-exported HTML for the landing page route. |

#### apps/web/ Config Files

| File | Purpose |
|---|---|
| `next.config.ts` | Next.js config — image domains, Sentry integration, CSP headers, experimental features. |
| `tailwind.config.ts` | Tailwind theme extensions — custom colours, spacing, font families. |
| `tsconfig.json` | TypeScript compiler options — strict mode, path aliases (`@/` → root). |
| `vitest.config.ts` | Vitest config — jsdom environment, setup file, coverage settings. |
| `playwright.config.ts` | Playwright E2E config — base URL, browser list, test directory. |
| `setupTests.ts` | Vitest global setup — imports `@testing-library/jest-dom` matchers. |
| `proxy.ts` | Dev proxy config for routing API calls to the local backend. |
| `package.json` | npm scripts, production and dev dependencies. |
| `package-lock.json` | Lockfile — committed to ensure reproducible installs. |

#### apps/web/ Sentry Files

| File | Purpose |
|---|---|
| `instrumentation.ts` | Next.js instrumentation hook — initialises Sentry on server startup. |
| `instrumentation-client.ts` | Client-side Sentry initialisation (runs in the browser). |
| `sentry.client.config.ts` | Sentry DSN, release, and client-side sampling config. |
| `sentry.server.config.ts` | Sentry server-side config (Node.js runtime). |
| `sentry.edge.config.ts` | Sentry edge runtime config (Vercel Edge Functions). |

#### apps/web/e2e/

| File | Purpose |
|---|---|
| `auth.spec.ts` | Playwright E2E test — covers sign-up, login, and auth callback flows. |

#### apps/web/\_\_tests\_\_/

| File | Purpose |
|---|---|
| `analyticsPhase2Utils.test.ts` | Vitest unit tests for analytics data transformation utilities. |

---

### apps/worker/ — Celery Worker

The worker process executes background tasks dispatched by the API.

| File | Purpose |
|---|---|
| `main.py` | Worker entry point — starts the Celery worker process, registers task modules. Run via `make worker`. |
| `sync_task.py` | `sync_account` task — fetches a fresh statement from the aggregator, runs ingestion, updates sync status. |
| `job_states.py` | Enum of training job state values (`QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`) shared between the API and worker. |
| `tests/test_sync_task.py` | Tests for the account sync task. |
| `tests/test_worker_jobs.py` | Tests for the training job dispatch and state transition logic. |

---

## packages/ — Shared ML/AI Libraries

These are pure Python packages imported by `apps/api/` and used standalone in tests. They have no dependency on FastAPI.

### packages/categorization/

The transaction categorisation engine. Uses a fine-tuned MiniLM v2 sentence transformer to classify transactions into spending categories. Supports per-user adapters (LoRA fine-tuning) trained from correction feedback.

| File | Purpose |
|---|---|
| `classifier.py` | Core classifier — loads the MiniLM model, runs inference, returns `(category, confidence)`. Checks `model_registry.py` for a user-specific adapter before falling back to the base model. |
| `cleaner.py` | Transaction text preprocessor — lowercases, strips noise tokens, normalises merchant names before classification. |
| `rules.py` | Rule-based override layer applied before the ML model — maps high-confidence patterns (e.g. "ATM withdrawal" → `Cash`) to categories without model inference. |
| `model_registry.py` | Resolves the correct model to use for a given user ID. Checks `user_model_metadata` in Supabase Storage for a fine-tuned adapter URL; falls back to the base MiniLM model. |
| `constants.py` | Category taxonomy — the fixed list of spending categories. |
| `cli.py` | Command-line interface for running classification on a CSV file (useful for batch evaluation). |
| `backends/base.py` | `ClassifierBackend` abstract base class. |
| `backends/cloud.py` | Cloud backend — runs inference via a remote endpoint (e.g. Modal) instead of locally. |
| `tests/test_classifier_v2.py` | Unit tests for the classifier (mock model, real preprocessing). |
| `tests/test_cleaner_v2.py` | Unit tests for the text cleaner. |
| `tests/test_rules_v2.py` | Unit tests for the rule override layer. |
| `tests/test_model_registry.py` | Unit tests for adapter resolution logic. |

### packages/forecasting/

Cash flow forecasting using a Temporal Fusion Transformer (TFT) model trained per-user on historical transaction data.

| File | Purpose |
|---|---|
| `tft_model.py` | TFT model definition using PyTorch Lightning. Configures encoder/decoder lengths, attention heads, and hidden sizes. |
| `trainer.py` | Training loop — prepares the dataset, instantiates the TFT, runs training epochs, saves the checkpoint to `checkpoints/`. |
| `dataset.py` | Dataset builder — transforms raw transaction rows into time series format suitable for the TFT. Handles resampling, missing values, and feature engineering (day-of-week, rolling averages). |
| `inference.py` | Loads a trained checkpoint and runs forward inference to produce a sequence of predicted daily spend/income values. |
| `requirements.txt` | Forecasting-specific Python deps (PyTorch Lightning, pytorch-forecasting) — a subset of the root `requirements.txt`. |
| `tests/test_dataset.py` | Tests for dataset construction from raw transactions. |
| `tests/test_dataset_features.py` | Tests for feature engineering logic (rolling means, seasonality flags). |
| `tests/test_inference.py` | Tests for inference output shape and value ranges. |
| `tests/test_model.py` | Tests for TFT model instantiation and forward pass. |
| `tests/test_scaling.py` | Tests that the normalisation scaler applies correctly to inputs and inverts on outputs. |
| `tests/test_timeseries_dataset.py` | Tests for the time series dataset wrapper. |
| `tests/test_trainer.py` | Tests for the training loop (uses a tiny synthetic dataset). |

### packages/ingestion_engine/

Parses bank statements from multiple formats (CSV, Excel, PDF statement text) and normalises them into the canonical transaction schema.

| File | Purpose |
|---|---|
| `parser.py` | Main entry point — detects file format, delegates to the appropriate sub-parser, returns a list of normalised `TransactionRecord` dicts. |
| `excel_parser.py` | Parses Excel (`.xlsx`) bank statement exports. Handles multi-sheet workbooks and header detection. |
| `merchant_extractor.py` | Extracts a clean merchant name from raw transaction description strings using regex patterns and a small lookup table. |
| `import_transactions.py` | Batch import utility — takes a list of parsed records and calls the API's `/ingest` endpoint. Used by scripts and the manual import flow. |
| `modal_app.py` | Modal serverless app definition — runs the ingestion pipeline on Modal's infrastructure for large batch imports. |
| `tests/test_csv_parsing.py` | Tests for CSV parser (various bank statement formats). |
| `tests/test_excel_parser.py` | Tests for Excel parser. |
| `tests/test_fingerprint.py` | Tests for the transaction deduplication fingerprint hash. |
| `tests/test_merchant_extractor.py` | Tests for merchant name extraction. |
| `tests/test_modal_handler.py` | Tests for the Modal app handler. |

---

## supabase/ — Database

### supabase/migrations/

All database migrations are timestamped SQL files applied via the Supabase CLI (`supabase db push`). They are append-only — never edit an existing migration.

| Migration | Purpose |
|---|---|
| `20260228000000_create_uploaded_files_table.sql` | Creates the `uploaded_files` table for tracking manual CSV/Excel imports. |
| `20260228010000_add_m2_indexes.sql` | Adds composite indexes to `transactions` for M2 query performance. |
| `20260228020000_tune_autovacuum_transactions.sql` | Tunes autovacuum settings on the `transactions` table for write-heavy workloads. |
| `20260301000000_user_model_metadata.sql` | Creates the `user_model_metadata` table — stores the Supabase Storage URL of each user's fine-tuned adapter. |
| `20260305000000_drop_deprecated_v1_tables.sql` | Drops V1 legacy tables no longer used after the domain refactor. |
| `20260309000000_add_transaction_fingerprint.sql` | Adds the `fingerprint` column to `transactions` and a unique constraint for deduplication. |
| `20260309000001_create_models_bucket.sql` | Creates the `models` Supabase Storage bucket for storing fine-tuned adapter files. |
| `20260309000002_add_training_lineage.sql` | Adds `parent_job_id` and `base_model_version` columns to `training_jobs` for lineage tracking. |
| `20260310000000_fix_fingerprint_unique.sql` | Fixes the fingerprint unique constraint scope (per-user, not global). |
| `20260315000000_create_bank_accounts_table.sql` | Creates the `bank_accounts` table with Setu consent reference and sync status. |
| `20260315000001_add_account_id_to_transactions.sql` | Adds `account_id` FK to `transactions` table. |
| `20260315000002_update_batch_import_rpc_account_id.sql` | Updates the `batch_import_transactions` RPC to accept and set `account_id`. |
| `20260316000001_fix_training_jobs_status_constraint.sql` | Fixes the `CHECK` constraint on `training_jobs.status` to match the full set of valid states. |
| `20260316000002_upsert_model_metadata_rpc.sql` | Adds the `upsert_user_model_metadata` RPC used by the training task to write adapter metadata after training completes. |

---

## scripts/ — Utility Scripts

One-off and maintenance scripts. Not part of the production code path.

| File | Purpose |
|---|---|
| `backfill_merchants.py` | Backfills `merchant_name` for existing transactions that pre-date the merchant extraction feature. Run once against production. |
| `cleanup_storage.py` | Deletes orphaned model files from Supabase Storage (adapters with no corresponding `user_model_metadata` row). |
| `evaluate_statement.py` | Runs the ingestion + categorisation pipeline against a local statement file and prints a classification report. Used for manual model evaluation. |
| `chaos_experiments.sh` | Shell script that kills processes and injects failures to validate resilience (see `docs/archive/sre/chaos-experiments.md`). |
| `check-refs.sh` | Validates that every `fix:` and `feat:` commit has a `Refs:` line pointing to a real `docs/` file. Run in CI. |
| `test-check-refs.sh` | Unit tests for `check-refs.sh`. |

---

## tests/ — Top-Level Test Suite

Contains integration tests that span multiple domains or packages, plus testing infrastructure.

Domain-specific unit tests live **co-located** with the domain code (e.g. `apps/api/domains/accounts/tests/`). Package-level tests live inside each package (e.g. `packages/categorization/tests/`). The top-level `tests/` directory is for cross-cutting integration tests.

---

## docs/ — Project Documentation

| Directory | Purpose |
|---|---|
| `docs/design/` | Living HLD documents — system architecture, API design, database design, codebase reference, AI tooling guide. Never archived; kept current. |
| `docs/features/` | Feature LLDs (auto-numbered 001, 002…). One per feature, from conception to verified. |
| `docs/bugs/` | Bug reports (BUG-NNN). Created before any fix is written. |
| `docs/adr/` | ADRs — recorded architectural decisions (ADR-NNN). |
| `docs/plans/` | Implementation plans (YYYY-MM-DD-name.md). Created from LLDs/ADRs before work begins. |
| `docs/policies/` | Standing policies — migration policy, secrets policy, etc. |
| `docs/investigations/` | Scratch notes for unconfirmed observations. Not formal docs; not committed as Bug Reports until confirmed. |
| `docs/archive/` | Superseded docs. Read-only. |
| `docs/STANDARDS.md` | The canonical documentation standard for all doc types, formats, and lifecycle rules. **Read this first.** |

---

## architecture/ — Schema References

| File | Purpose |
|---|---|
| `schema.sql` | Reference SQL schema (not a migration — for documentation and new-environment bootstrapping). |
| `training_schema.sql` | Schema for training-related tables. |
| `ingestion.md` | Notes on the ingestion data flow and schema decisions. |
| `navigation.md` | Notes on frontend navigation architecture decisions. |
| `verify_schema.py` | Script to diff the reference schema against the live Supabase schema. |
| `migrations/` | Legacy migration reference files (pre-Supabase CLI). Superseded by `supabase/migrations/`. |

---

## assets/

| Directory | Purpose |
|---|---|
| `templates/` | HTML/CSS templates used for email notifications or landing page prototypes. |

---

## backups/

Contains local backups of the categorisation engine (V1 artefacts). The active engine is in `packages/categorization/`.

| Directory | Purpose |
|---|---|
| `categorization_engine_v1/` | Archive of the V1 classifier implementation, kept for reference during the V2 migration. |

---

## checkpoints/

Local storage for TFT model training checkpoints. Created at runtime by `packages/forecasting/trainer.py`. Gitignored. Mounted into the Docker worker container.

---

## references/

Reference material used during development — not runtime code.

| Directory | Purpose |
|---|---|
| `reference_html/` | Scraped or exported HTML pages used as visual references for UI design decisions. |
| `reference_txt/` | Plain-text reference documents (API docs, spec extracts, etc.). |

---

## tools/

| Directory | Purpose |
|---|---|
| `scripts/` | Additional developer tooling scripts (separate from root `scripts/` — generally for local dev use). |
| `tests/` | Tests for the tooling scripts themselves. |

---

## Hidden and Tooling Directories (summarised)

These directories contain AI assistant configuration, CI/CD, and development tooling. They are not part of the product runtime.

| Directory | Purpose | Details |
|---|---|---|
| `.claude/` | Claude Code configuration — rules, workflows, skills, settings | See [`ai-tooling-guide.md`](ai-tooling-guide.md) |
| `.gemini/` | Gemini CLI context, rules, and knowledge files | See [`ai-tooling-guide.md`](ai-tooling-guide.md) |
| `.github/` | GitHub Actions CI/CD workflows and Dependabot config | See [`ai-tooling-guide.md`](ai-tooling-guide.md) |
| `.git/` | Git object store — managed by Git, never edit manually | — |
| `.venv/` | Python virtual environment — gitignored, recreated via `make install` | — |
| `.next/` | Next.js build output — gitignored, recreated via `npm run build` | — |
| `.superpowers/` | Superpowers plugin cache — managed by the Claude Code superpowers plugin | — |
| `.vercel/` | Vercel CLI project metadata — gitignored | — |
| `.pytest_cache/` | pytest cache — gitignored | — |
| `.ruff_cache/` | Ruff linter cache — gitignored | — |

---

## Changelog

| Date | Change |
|---|---|
| 2026-04-03 | Initial version created for team onboarding (Hassan + Jessica). |
