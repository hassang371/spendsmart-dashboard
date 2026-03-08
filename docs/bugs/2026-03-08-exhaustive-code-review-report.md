# SCALE App Exhaustive Code Review Report

Date: 2026-03-08
Reviewer: OpenCode (automated + manual-assisted review)
Workspace: `SCALE APP`

## Executive Summary

This review covered the application backend, frontend, shared packages, ingestion scripts, migrations, Docker setup, and CI/CD workflows.

- Reviewed files: ~777 non-cache files
- Automated checks run:
  - `pytest -q` -> **116 passed**, 85 warnings
  - `.venv/bin/python -m compileall -q apps packages tools` -> **passed**
  - `npm run lint` in `apps/web` -> **4 errors, 110 warnings**
- Highest-risk themes:
  1. Multi-tenant isolation and auth failure-path robustness
  2. Forecast inference runtime correctness
  3. CI/CD security gate weaknesses
  4. Data safety issues in destructive migration and storage handling

## Scope and Methodology

### Scope

- Backend: `apps/api`, `apps/worker`
- Frontend: `apps/web`
- Shared packages: `packages/categorization`, `packages/forecasting`, `packages/ingestion_engine`
- Ops/config: `.github/workflows`, `docker-compose.yml`, `Dockerfile`, `supabase/migrations`, `tools`

### Exclusions

- Generated/cache artifacts (`__pycache__`, `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, etc.)
- Historical backup code was scanned opportunistically but not treated as production authority unless issue pattern appeared in active code as well.

### Approach

1. Full-file inventory and targeted static review.
2. Specialized subsystem deep review (API, packages, frontend, infra/workflows).
3. Runtime signal collection from tests/lint/compile checks.
4. Consolidation into severity-ranked findings with concrete fixes.

## Severity Legend

- **Critical**: likely to cause security breach, major outage, or unguarded production failure path.
- **High**: serious correctness/security/reliability risk with meaningful blast radius.
- **Medium**: notable logic/quality risk that can break workflows or create data inconsistency.
- **Low**: maintainability gaps, weak patterns, or localized defects.

## Findings (Exhaustive)

### Critical

#### BUG-001 — Deploy workflow does not truly gate on CI status
- Severity: **Critical**
- File: `.github/workflows/deploy.yml:17`
- Category: CI/CD, release safety
- Issue:
  - `wait-for-ci` only prints `"CI passed — proceeding to deploy."` and does not verify check status.
- Why this matters:
  - Deployment can proceed even when CI/security checks fail (especially if branch protection is weak/misconfigured).
- Recommended fix:
  - Convert deploy trigger to `workflow_run` on successful CI, or add an explicit status-check step via GitHub API and fail when CI is not green.
  - Add workflow-level `permissions:` with minimum required scopes.
- Verification:
  - Simulate failed CI on a branch and confirm deploy does not execute.

### High

#### BUG-002 — Cross-tenant data exposure risk in safe-to-spend query
- Severity: **High**
- File: `apps/api/domains/forecasting/router.py:123`
- Category: Security, multi-tenancy
- Issue:
  - Query on `transactions` is missing `.eq("user_id", user_id)`.
- Why this matters:
  - Forecast calculation may include other users' transactions.
- Recommended fix:
  - Add user filter before date filter/order.
  - Add regression test proving only authenticated user rows are returned.

#### BUG-003 — JWT `exp` type handling can crash auth path
- Severity: **High**
- File: `apps/api/core/auth.py:103`
- Category: Auth, error handling
- Issue:
  - `time.time() > (exp + CLOCK_SKEW_SECONDS)` assumes numeric `exp`.
  - Non-numeric `exp` can raise `TypeError`, causing 500.
- Why this matters:
  - Malformed token yields server error instead of controlled 401.
- Recommended fix:
  - Normalize claim type (`exp_int = int(exp)`) under guarded parsing.
  - On parse/type failure, return 401 with structured error.
- Verification:
  - Add tests for string/non-numeric `exp` claims.

#### BUG-004 — Forecast inference dataset API misuse
- Severity: **High**
- File: `packages/forecasting/inference.py:189`
- Category: Runtime correctness
- Issue:
  - `TimeSeriesDataSet.from_dataset` is called with `model.dataset_parameters` (dict) instead of a dataset instance.
- Why this matters:
  - Can fail at runtime during prediction dataset construction.
- Recommended fix:
  - Persist and pass the training `TimeSeriesDataSet` object (or rebuild proper dataset object before calling `from_dataset`).
- Verification:
  - Add integration test using real `TimeSeriesDataSet` path (not mocked API contract).

#### BUG-005 — Forecast horizon loop can index out of bounds
- Severity: **High**
- File: `packages/forecasting/inference.py:219`
- Category: Runtime correctness
- Issue:
  - Loop uses `range(horizon)` without guarding against actual prediction length.
- Why this matters:
  - `IndexError` if requested horizon exceeds model output.
- Recommended fix:
  - Clamp by predicted length or validate horizon against model configuration.

#### BUG-006 — Personalization adapter training not applied at inference
- Severity: **High**
- File: `packages/categorization/classifier.py:215`
- Category: ML logic correctness
- Issue:
  - Adapter training pipeline exists, but prediction path does not consume adapter logits.
- Why this matters:
  - User corrections do not affect real predictions.
- Recommended fix:
  - Integrate adapter scoring in `predict`/`predict_batch` and document blending/override strategy.
  - Add tests proving corrections change predicted label.

#### BUG-007 — Hard dependency import blocks plain Excel parsing
- Severity: **High**
- File: `packages/ingestion_engine/excel_parser.py:2`
- Category: Dependency robustness
- Issue:
  - `msoffcrypto` imported at module load.
- Why this matters:
  - Environments lacking decryption dependency cannot parse unencrypted `.xlsx`.
- Recommended fix:
  - Lazy import only for encrypted-path handling; raise actionable error only when decryption is needed.

#### BUG-008 — Security scan failure is downgraded to warning
- Severity: **High**
- File: `.github/workflows/ci.yml:53`
- Category: CI security
- Issue:
  - `pip-audit -r requirements.txt || echo "Warning: Vulnerabilities found"`
- Why this matters:
  - Known vulnerabilities do not fail CI.
- Recommended fix:
  - Remove fallback suppression and fail on findings; maintain temporary allowlist with expiry if needed.

#### BUG-009 — Floating action refs in security-sensitive CI steps
- Severity: **High**
- Files:
  - `.github/workflows/ci.yml:34` (`trufflesecurity/trufflehog@main`)
  - `.github/workflows/ci.yml:91` (`aquasecurity/trivy-action@master`)
- Category: Supply chain, CI integrity
- Issue:
  - Uses mutable refs.
- Why this matters:
  - Non-reproducible builds and upstream tampering/update risk.
- Recommended fix:
  - Pin each third-party action to immutable commit SHA.

#### BUG-010 — Storage quota fallback clears entire origin storage
- Severity: **High**
- File: `apps/web/lib/utils/cache.ts:77`
- Category: Frontend data integrity
- Issue:
  - On quota exceeded, code calls `storage.clear()`.
- Why this matters:
  - Can wipe unrelated app/browser state for same origin, including session-related keys.
- Recommended fix:
  - Implement prefix-based targeted eviction for app-owned cache keys.

#### BUG-011 — Login social button can accidentally submit form
- Severity: **High**
- File: `apps/web/app/login/page.tsx:238`
- Category: UX logic correctness
- Issue:
  - Button inside form does not declare `type="button"`.
- Why this matters:
  - Click may trigger both OAuth flow and form submit/validation.
- Recommended fix:
  - Set `type="button"` and keep explicit click handler.

#### BUG-012 — Destructive migration uses `CASCADE` drop
- Severity: **High**
- File: `supabase/migrations/20260305000000_drop_deprecated_v1_tables.sql:4`
- Category: Data safety, migrations
- Issue:
  - `DROP TABLE ... CASCADE` can remove dependent objects implicitly.
- Why this matters:
  - High blast radius and potential irreversible data/model breakages.
- Recommended fix:
  - Remove cascade; explicitly remove/replace dependencies.
  - Run pre-migration backup and include tested rollback script.

#### BUG-013 — Operational exposure in local infra defaults (Redis/Flower)
- Severity: **High**
- File: `docker-compose.yml:5` and `docker-compose.yml:82`
- Category: DevOps security
- Issue:
  - Redis and Flower are host-exposed; Flower auth safety depends on env being non-empty.
- Why this matters:
  - Unauthorized local/network access risk and metadata leakage.
- Recommended fix:
  - Bind to localhost/internal network only.
  - Enforce required auth env vars and fail startup when missing.

### Medium

#### BUG-014 — Invalid cursor likely returns 500 instead of 400
- Severity: **Medium**
- File: `apps/api/domains/accounts/service.py:48`
- Category: API error handling
- Issue:
  - `decode_cursor` exceptions are not translated to client-safe error.
- Why this matters:
  - User input errors become internal server errors.
- Recommended fix:
  - Catch decode errors and raise `HTTPException(400, "Invalid cursor")`.

#### BUG-015 — Duplicate marker inserted before parse completion
- Severity: **Medium**
- File: `apps/api/domains/forecasting/router.py:52`
- Category: Ingestion/retry semantics
- Issue:
  - Duplicate file fingerprint appears to be recorded before parsing succeeds.
- Why this matters:
  - Parse failure can block valid retry of same file.
- Recommended fix:
  - Record marker after successful parse/validation or rollback marker on failure.

#### BUG-016 — Unhandled `Content-Length` parse failure path
- Severity: **Medium**
- File: `apps/api/main.py:66`
- Category: Request robustness
- Issue:
  - `int(content_length)` can raise on malformed header.
- Why this matters:
  - Invalid client input may cause 500.
- Recommended fix:
  - Guard parse and return 400 with problem details.

#### BUG-017 — Cleanup task references mismatched job table
- Severity: **Medium**
- File: `apps/api/core/tasks/maintenance_tasks.py:32`
- Category: Background operations
- Issue:
  - Task updates `classification_jobs` while system primarily uses `training_jobs`.
- Why this matters:
  - Stale-job cleanup may not touch active job records.
- Recommended fix:
  - Align naming/schema and update tests/scheduler mappings.

#### BUG-018 — Worker failure path can leave jobs stuck in processing
- Severity: **Medium**
- File: `apps/worker/main.py:155`
- Category: Reliability
- Issue:
  - Failure-status write is not robust if secondary DB update fails.
- Why this matters:
  - Zombie jobs and operational toil.
- Recommended fix:
  - Wrap failure-status update in nested try/except and add retry/backoff.

#### BUG-019 — Batch transaction update semantics diverge from single update
- Severity: **Medium**
- File: `apps/api/domains/accounts/router.py:253`
- Category: Data consistency
- Issue:
  - Batch path updates fewer fields than single-item path (`is_manual`, `suggested_category`, `confidence_score` handling mismatch).
- Why this matters:
  - Inconsistent downstream analytics/training behavior.
- Recommended fix:
  - Reuse a common update payload builder shared by single and batch operations.

#### BUG-020 — Potential duplicate canonical column names in parser
- Severity: **Medium**
- File: `packages/ingestion_engine/parser.py:567`
- Category: Parser correctness
- Issue:
  - Multiple source columns can normalize to same canonical name.
- Why this matters:
  - Ambiguous row values and skipped/incorrect parses.
- Recommended fix:
  - Deterministic de-duplication/priority rules for canonical columns.

#### BUG-021 — Amount parsing misses common DR/CR text formats
- Severity: **Medium**
- File: `packages/ingestion_engine/parser.py:639`
- Category: Parser correctness
- Issue:
  - Values like `1234.00CR` / `1234.00DR` are not normalized.
- Why this matters:
  - Rows parse to 0 or wrong sign, leading to data loss/inaccuracy.
- Recommended fix:
  - Normalize suffix/prefix credit/debit patterns before numeric conversion.

#### BUG-022 — Signed amount derivation can ignore debit/credit columns
- Severity: **Medium**
- File: `packages/ingestion_engine/parser.py:656`
- Category: Parser business logic
- Issue:
  - Existing `amount` column can bypass debit/credit-based sign derivation.
- Why this matters:
  - Sign errors when source provides separate debit/credit with ambiguous amount.
- Recommended fix:
  - Prefer debit/credit inference when both columns are present.

#### BUG-023 — CSV decoding path is UTF-8 only
- Severity: **Medium**
- File: `packages/ingestion_engine/import_transactions.py:235`
- Category: Input compatibility
- Issue:
  - Non-UTF8 CSV files may fail despite being valid bank exports.
- Why this matters:
  - Import failures for real-world user files.
- Recommended fix:
  - Add fallback encoding strategy (e.g., latin-1/cp1252) with safe logging.

#### BUG-024 — Settings page cache invalidation bypasses cache key scheme
- Severity: **Medium**
- File: `apps/web/app/dashboard/settings/page.tsx:263`
- Related file: `apps/web/lib/utils/cache.ts:7`
- Category: Frontend consistency
- Issue:
  - Settings page removes unprefixed keys directly while cache utility uses `dev:`/`prod:` prefix.
- Why this matters:
  - Stale cached cards/data can persist after destructive actions.
- Recommended fix:
  - Use `removeCachedData` helper consistently for all cache keys.

#### BUG-025 — API client assumes all successful responses contain JSON
- Severity: **Medium**
- File: `apps/web/lib/api/client.ts:209`
- Category: Frontend API robustness
- Issue:
  - `response.json()` is unconditional on success.
- Why this matters:
  - `204 No Content` success responses can throw parse errors.
- Recommended fix:
  - Handle empty-body/204 separately before JSON parsing.

#### BUG-026 — Client-side data fetch limits can silently truncate analytics
- Severity: **Medium**
- Files:
  - `apps/web/app/dashboard/page.tsx:87`
  - `apps/web/app/dashboard/analytics/page.tsx:65`
- Category: Data correctness
- Issue:
  - Hard limit (`500`) can truncate user transaction basis.
- Why this matters:
  - Incorrect totals/charts for heavier accounts.
- Recommended fix:
  - Cursor-pagination aggregation or backend aggregate endpoints; show truncation warning if capped.

#### BUG-027 — CSV export formula injection risk
- Severity: **Medium**
- File: `apps/web/app/dashboard/settings/page.tsx:156`
- Category: Security (output handling)
- Issue:
  - Export does not sanitize spreadsheet formula-leading characters (`=`, `+`, `-`, `@`).
- Why this matters:
  - Potential formula execution when opening exported CSV in spreadsheet software.
- Recommended fix:
  - Prefix dangerous-leading values with `'` before CSV serialization.

#### BUG-028 — Performance workflow readiness check is time-based and flaky
- Severity: **Medium**
- File: `.github/workflows/performance.yml:29`
- Category: CI reliability
- Issue:
  - Uses fixed sleep rather than health-check polling.
- Why this matters:
  - False failures/noisy performance numbers.
- Recommended fix:
  - Poll health endpoint with timeout/retry before starting k6.

#### BUG-029 — Index migration may lock writes on large tables
- Severity: **Medium**
- File: `supabase/migrations/20260228_add_m2_indexes.sql:5`
- Category: DB operations
- Issue:
  - Index creation not marked `CONCURRENTLY`.
- Why this matters:
  - Potential lock contention and write interruption during migration windows.
- Recommended fix:
  - Use `CREATE INDEX CONCURRENTLY` in non-transactional migration.

#### BUG-030 — Bulk import is non-idempotent and partially durable
- Severity: **Medium**
- File: `tools/scripts/import_transactions.py:113`
- Category: Data integrity
- Issue:
  - Insert-only behavior and chunk-level error handling can create duplicates/partial state on retries.
- Why this matters:
  - Corrupt analytics and hard-to-reconcile imports.
- Recommended fix:
  - Add deterministic fingerprint + unique constraint + upsert semantics; consider staging then finalize.

### Low

#### BUG-031 — Rate limiter identity key may collide
- Severity: **Low**
- File: `apps/api/core/rate_limiter.py:27`
- Category: Reliability
- Issue:
  - Uses token suffix for keying.
- Why this matters:
  - Rare collision can throttle unrelated users.
- Recommended fix:
  - Key from verified subject (`sub`) or secure hash of full stable identity.

#### BUG-032 — Anomaly route shape encourages insecure usage pattern
- Severity: **Low**
- File: `apps/api/domains/anomaly/router.py:8`
- Category: API design
- Issue:
  - Accepts path `user_id` and lacks auth dependency in current shape.
- Why this matters:
  - IDOR-prone API pattern if expanded without guardrails.
- Recommended fix:
  - Remove path user id and derive from authenticated context.

#### BUG-033 — Worker tests are mostly structural, not behavioral
- Severity: **Low**
- File: `apps/worker/tests/test_worker_jobs.py:14`
- Category: Test quality
- Issue:
  - Tests mainly assert callability/existence, not lifecycle behavior.
- Why this matters:
  - Regressions in claim/transition/failure handling can pass unnoticed.
- Recommended fix:
  - Add behavior tests for claim race, success transition, and failure-to-failed-status path.

#### BUG-034 — Frontend lint has hard errors in transactions page
- Severity: **Low** (build quality), can become **Medium** if CI blocks merges
- File: `apps/web/app/dashboard/transactions/page.tsx`
- Category: Maintainability
- Issue:
  - Unused variables (`monthLookup`, `toTitleCase`, `setUpdatingCategory`) and `!=` operator violation.
- Why this matters:
  - Reduced quality signal and potential stale/dead code.
- Recommended fix:
  - Remove unused symbols, enforce strict comparisons, and tighten types.

#### BUG-035 — CI workflow lacks explicit least-privilege permissions
- Severity: **Low**
- File: `.github/workflows/ci.yml:1`
- Category: CI hardening
- Issue:
  - No explicit `permissions:` block.
- Why this matters:
  - Token scopes may be broader than necessary depending repository defaults.
- Recommended fix:
  - Add global and per-job minimum permissions.

## Additional Observations

### Test/Warning Signals

- `pytest` passed, but warnings include:
  - Pydantic deprecation warnings in dependencies
  - Lightning/Sklearn warnings in forecasting tests
  - Date parsing warning in ingestion tests
- These are not immediate blockers but should be tracked for future dependency upgrades and behavior consistency.

### Frontend Lint Summary

- `apps/web` lint currently reports:
  - 4 errors
  - 110 warnings
- Main quality themes:
  - `no-explicit-any`
  - heavy `console` usage
  - hook dependency warnings
  - dead code in transactions page

## Prioritized Remediation Plan

### P0 (Immediate)

1. BUG-002 (tenant filter in safe-to-spend)
2. BUG-003 (JWT `exp` type-safe handling)
3. BUG-004 + BUG-005 (forecast inference runtime fixes)
4. BUG-001 + BUG-008 + BUG-009 (CI/deploy gate and security pinning)
5. BUG-012 (safe migration plan for destructive changes)

### P1 (This Sprint)

1. BUG-010 + BUG-024 + BUG-025 (frontend cache/API robustness)
2. BUG-018 + BUG-017 + BUG-019 (job lifecycle and consistency)
3. BUG-020/021/022/023 (parser correctness and compatibility)
4. BUG-027 (CSV formula injection mitigation)

### P2 (Hardening Backlog)

1. BUG-029 + BUG-030 (data/DB operational resilience)
2. BUG-031 + BUG-032 + BUG-033 + BUG-034 + BUG-035 (quality and architecture hardening)

## Regression Test Checklist (Recommended)

- Backend:
  - Auth tests for malformed `exp` claim types.
  - Safe-to-spend tests asserting strict user scoping.
  - Cursor error-path tests returning 400.
  - Worker tests for status transitions under failure and secondary update failures.
- Packages:
  - Inference integration test with real `TimeSeriesDataSet` object.
  - Horizon bounds tests for forecast response formatting.
  - Parser fixtures for duplicate canonical columns and DR/CR formats.
  - Encoding fallback tests for non-UTF8 CSV imports.
- Frontend:
  - Login social button interaction test (no accidental submit).
  - API client test for 204 success response.
  - Cache invalidation tests using env-prefixed keys.
  - CSV export sanitization test for formula-leading values.
- CI/CD:
  - Failing CI scenario should block deploy.
  - Vulnerability finding should fail pipeline.

## Notes and Limitations

- This report combines static review + available runtime checks; findings are prioritized for engineering action.
- Some infra risks (network exposure, deployment guardrails) depend on environment settings and should be validated against actual production/staging configuration.
- Historical backup folders were not the primary deployment target but were useful for pattern detection.
