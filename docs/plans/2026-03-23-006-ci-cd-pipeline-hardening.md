# CI/CD Pipeline Hardening (LLD 006) Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the CI pipeline by adding missing security scans, coverage gates, branch triggers, GHCR image push, pre-commit hooks, and Playwright E2E as specified in LLD 006.

**Architecture:** Changes span three file classes — GitHub Actions workflows (ci.yml), developer tooling (.pre-commit-config.yaml, check-refs.sh, commitlint), and config files (dependabot.yml, playwright.config.ts). Each task is independently verifiable and committable.

**Tech Stack:** GitHub Actions, Docker/GHCR, Playwright, Vitest + @vitest/coverage-v8, pytest-cov, CodeQL, pre-commit, commitlint, ruff 0.3.3, Bandit, Trivy

---

## File Map

| Action | File | What changes |
|---|---|---|
| MODIFY | `.github/workflows/ci.yml` | Branch trigger, concurrency, timeouts, Bandit hard-fail, ruff pin, ESLint, npm audit, coverage thresholds, next build, CodeQL job, dependency-review job, test-e2e job, GHCR push (rename build job) |
| MODIFY | `.pre-commit-config.yaml` | Add detect-private-key, detect-aws-credentials, frontend-typecheck, prettier-check, commitlint (commit-msg), check-refs (commit-msg) |
| CREATE | `scripts/check-refs.sh` | Rejects fix:/feat: commits lacking a `Refs: docs/` line |
| CREATE | `scripts/test-check-refs.sh` | Shell test suite for check-refs.sh |
| CREATE | `.commitlintrc.json` | Conventional commit format config |
| MODIFY | `requirements.txt` | Add `pytest-cov==6.0.0` |
| MODIFY | `apps/web/package.json` | Add `@vitest/coverage-v8`, `@commitlint/cli`, `@commitlint/config-conventional` dev dependencies |
| MODIFY | `apps/web/vitest.config.ts` | Add `coverage` block with `provider: 'v8'` and `thresholds.lines: 60` |
| MODIFY | `pyproject.toml` | Add `[tool.bandit]` section (required for hard-fail Bandit step) |
| MODIFY | `apps/web/playwright.config.ts` | Add `webServer.timeout: 120_000` |
| CREATE | `.github/dependabot.yml` | Weekly auto-PRs for npm, pip, github-actions |
| MODIFY | `docs/design/system-architecture.md` | Add GHCR registry to Infrastructure subgraph + Changelog |
| MODIFY | `docs/features/006-ci-cd-pipeline-hardening.md` | Status: Draft → Implemented |

---

## Chunk 1: Pre-commit Hooks

### Task 1: Secret detection hooks

**Files:**
- Modify: `.pre-commit-config.yaml`

Adds `detect-private-key` and `detect-aws-credentials` to the existing `pre-commit-hooks` block. These hook into the pre-commit stage and block commits containing private key PEM patterns or AWS credential patterns.

- [ ] **Step 1: Verify these hooks are not already present**

```bash
grep -E "detect-private-key|detect-aws-credentials" .pre-commit-config.yaml
```

Expected: no output (hooks not present yet)

- [ ] **Step 2: Add hooks to `.pre-commit-config.yaml`**

In `.pre-commit-config.yaml`, find the `pre-commit-hooks` block (first repo entry). Add two new hooks at the end of that block's `hooks:` list:

```yaml
      - id: detect-private-key
      - id: detect-aws-credentials
        args: [--allow-missing-credentials]
```

`--allow-missing-credentials` prevents false failures on machines without AWS credentials configured locally — it only fails if credentials are literally embedded in tracked files.

After the edit, the full pre-commit-hooks block looks like:

```yaml
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
        exclude: \.svg$
      - id: check-merge-conflict
      - id: check-json
      - id: check-yaml
        args: [--multi]
      - id: check-toml
      - id: check-added-large-files
      - id: detect-private-key
      - id: detect-aws-credentials
        args: [--allow-missing-credentials]
```

- [ ] **Step 3: Run hooks — expect no false positives**

```bash
pre-commit run detect-private-key --all-files
pre-commit run detect-aws-credentials --all-files
```

Expected: both exit 0 with "Passed" or no output

- [ ] **Step 4: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add detect-private-key and detect-aws-credentials pre-commit hooks"
```

---

### Task 2: TypeScript + Prettier pre-commit hooks

**Files:**
- Modify: `.pre-commit-config.yaml`

Adds `tsc --noEmit` (catches TS type errors before push) and `prettier --check` (enforces formatting) as local pre-commit hooks. Both run only on TypeScript/JavaScript file changes.

- [ ] **Step 1: Verify tsc is clean before adding the hook**

```bash
cd apps/web && npx tsc --noEmit
```

Expected: exits 0, no output. If there are type errors, fix them first before adding the hook.

- [ ] **Step 2: Add tsc and prettier hooks to the existing `repo: local` block**

Find the existing `repo: local` block in `.pre-commit-config.yaml` (it has `frontend-lint`). Add two new hooks to the same block:

```yaml
  - repo: local
    hooks:
      - id: frontend-lint
        name: Frontend Lint (Next.js)
        entry: bash -c 'cd apps/web && npm run lint'
        language: system
        types_or: [javascript, jsx, ts, tsx]
        pass_filenames: false
        stages: [pre-commit]
      - id: frontend-typecheck
        name: Frontend TypeScript Check
        entry: bash -c 'cd apps/web && npx tsc --noEmit'
        language: system
        types_or: [ts, tsx]
        pass_filenames: false
        stages: [pre-commit]
      - id: prettier-check
        name: Prettier Format Check
        entry: bash -c 'cd apps/web && npx prettier --check .'
        language: system
        types_or: [javascript, jsx, ts, tsx, css, json]
        pass_filenames: false
        stages: [pre-commit]
```

- [ ] **Step 3: Verify `.prettierignore` exists in `apps/web/`**

```bash
ls apps/web/.prettierignore 2>/dev/null || echo "MISSING"
```

If `MISSING`: create `apps/web/.prettierignore` with at minimum:

```
.next/
node_modules/
next-env.d.ts
```

This prevents Prettier from checking generated files which would cause false failures.

- [ ] **Step 4: Run both hooks — expect no false positives**

```bash
pre-commit run frontend-typecheck --all-files
pre-commit run prettier-check --all-files
```

Expected: both pass. If prettier fails on source files, run `cd apps/web && npx prettier --write .` first, commit the formatting fix, then re-run.

- [ ] **Step 5: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add tsc and prettier pre-commit hooks"
```

---

### Task 3: check-refs.sh + commitlint (commit-msg stage)

**Files:**
- Create: `scripts/check-refs.sh`
- Create: `scripts/test-check-refs.sh`
- Create: `.commitlintrc.json`
- Modify: `.pre-commit-config.yaml`

`check-refs.sh` implements the Documentation Gate 4 enforcement: any commit with prefix `fix:` or `feat:` must include a `Refs: docs/...` line pointing to a file that actually exists. `commitlint` enforces conventional commit format at the `commit-msg` stage.

- [ ] **Step 1: Write the test suite first (TDD)**

Create `scripts/test-check-refs.sh`:

```bash
#!/usr/bin/env bash
# Test suite for check-refs.sh — run with: bash scripts/test-check-refs.sh
set -e

SCRIPT="$(dirname "$0")/check-refs.sh"
PASS=0
FAIL=0

run_test() {
  local name="$1" msg="$2" expected_exit="$3"
  local tmpfile
  tmpfile=$(mktemp)
  printf "%s" "$msg" > "$tmpfile"
  bash "$SCRIPT" "$tmpfile" >/dev/null 2>&1
  local actual_exit=$?
  rm -f "$tmpfile"
  if [ "$actual_exit" -eq "$expected_exit" ]; then
    echo "PASS: $name"
    PASS=$((PASS + 1))
  else
    echo "FAIL: $name (expected exit $expected_exit, got $actual_exit)"
    FAIL=$((FAIL + 1))
  fi
}

# fix: without Refs: → must fail
run_test "fix without refs" "fix: something broken" 1

# feat: without Refs: → must fail
run_test "feat without refs" "feat: add feature" 1

# fix: with valid Refs: pointing to real file → must pass
REAL_DOC="docs/features/006-ci-cd-pipeline-hardening.md"
MSG="fix: something broken

Refs: ${REAL_DOC}"
run_test "fix with valid refs" "$MSG" 0

# fix: with Refs: pointing to non-existent file → must fail
MSG_MISSING="fix: something broken

Refs: docs/bugs/BUG-999-nonexistent.md"
run_test "fix with missing file" "$MSG_MISSING" 1

# chore: without Refs: → must pass (not required)
run_test "chore without refs" "chore: update deps" 0

# docs: without Refs: → must pass
run_test "docs without refs" "docs: update README" 0

# Merge commit → must pass
run_test "merge commit" "Merge branch 'feat/foo' into 'main'" 0

# fix: with Refs: pointing outside docs/ → must fail (only docs/ paths accepted)
MSG_OUTSIDE="fix: something broken

Refs: scripts/check-refs.sh"
run_test "fix with refs outside docs/" "$MSG_OUTSIDE" 1

# fix: with Refs: line present but empty path → must fail
MSG_EMPTY="fix: something broken

Refs: "
run_test "fix with empty refs path" "$MSG_EMPTY" 1

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
```

Make executable:

```bash
chmod +x scripts/test-check-refs.sh
```

- [ ] **Step 2: Run test suite — expect failure (script missing)**

```bash
bash scripts/test-check-refs.sh
```

Expected: multiple `FAIL:` lines and `Results: 0 passed, N failed` (script doesn't exist yet so all invocations fail)

- [ ] **Step 3: Implement `scripts/check-refs.sh`**

```bash
#!/usr/bin/env bash
# check-refs.sh — commit-msg hook
# Rejects fix:/feat: commits that lack a "Refs: docs/" line pointing to a real file.
#
# Usage (pre-commit passes commit message file path as $1):
#   bash scripts/check-refs.sh <commit-msg-file>

set -euo pipefail

COMMIT_MSG_FILE="$1"
FIRST_LINE=$(head -1 "$COMMIT_MSG_FILE")

# Only enforced on fix: and feat: prefixes
if [[ "$FIRST_LINE" != fix:* && "$FIRST_LINE" != feat:* ]]; then
  exit 0
fi

# Look for a "Refs: docs/" line anywhere in the message
REFS_LINE=$(grep -E '^Refs: docs/' "$COMMIT_MSG_FILE" || true)

if [ -z "$REFS_LINE" ]; then
  echo "ERROR: fix:/feat: commits require a 'Refs: docs/...' line."
  echo ""
  echo "Example:"
  echo "  fix: describe the fix"
  echo ""
  echo "  Refs: docs/bugs/BUG-NNN-name.md"
  exit 1
fi

# Extract path and verify the file exists
REFS_PATH=$(echo "$REFS_LINE" | sed 's/^Refs: //' | xargs)
if [ -z "$REFS_PATH" ]; then
  echo "ERROR: Refs: line is present but the path is empty."
  exit 1
fi
if [ ! -f "$REFS_PATH" ]; then
  echo "ERROR: Refs: points to non-existent file: $REFS_PATH"
  exit 1
fi

exit 0
```

Make executable:

```bash
chmod +x scripts/check-refs.sh
```

- [ ] **Step 4: Run test suite — expect 9/9 pass**

```bash
bash scripts/test-check-refs.sh
```

Expected: `Results: 9 passed, 0 failed`

- [ ] **Step 5: Create `.commitlintrc.json`**

```json
{
  "extends": ["@commitlint/config-conventional"],
  "rules": {
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "docs", "test", "refactor", "chore", "revert"]
    ]
  }
}
```

- [ ] **Step 6: Add `@commitlint/cli` and `@commitlint/config-conventional` to `apps/web/package.json`**

Per LLD 006 Section 3 (Scope), these must be in `apps/web/package.json` so `npx commitlint` is available locally for manual verification:

```bash
cd apps/web && npm install --save-dev @commitlint/cli @commitlint/config-conventional
```

Verify the entries appear in devDependencies:

```bash
grep -E "@commitlint" apps/web/package.json
```

Expected: two entries in devDependencies.

- [ ] **Step 7: Add commitlint and check-refs hooks to `.pre-commit-config.yaml`**

Add a new repo block for commitlint (uses `language: node` — pre-commit installs deps automatically from `additional_dependencies`). Use rev `v19.6.1` which is the stable v19 release tag that exists in the commitlint repository:

```yaml
  - repo: https://github.com/conventional-changelog/commitlint
    rev: v19.6.1
    hooks:
      - id: commitlint
        stages: [commit-msg]
        additional_dependencies: ['@commitlint/config-conventional@19.6.1']
```

Also add the `check-refs` hook to the existing `repo: local` block (inside the `hooks:` list, after `prettier-check`):

```yaml
      - id: check-refs
        name: Check Refs line on fix/feat commits
        entry: bash scripts/check-refs.sh
        language: system
        stages: [commit-msg]
```

- [ ] **Step 8: Install commit-msg hook stage**

Pre-commit's `commit-msg` stage is not active until explicitly installed. Run:

```bash
pre-commit install --hook-type commit-msg
```

Then verify both stages are active:

```bash
ls .git/hooks/commit-msg .git/hooks/pre-commit
```

Expected: both files exist.

- [ ] **Step 9: Verify the manual check-refs invocation works**

```bash
TMPFILE=$(mktemp)
echo "fix: test without refs" > "$TMPFILE" && bash scripts/check-refs.sh "$TMPFILE"; rm -f "$TMPFILE"
```

Expected: exit 1 with error message

```bash
TMPFILE=$(mktemp)
printf "fix: test with refs\n\nRefs: docs/features/006-ci-cd-pipeline-hardening.md" > "$TMPFILE" && bash scripts/check-refs.sh "$TMPFILE"; rm -f "$TMPFILE"
```

Expected: exit 0 (silent)

- [ ] **Step 10: Commit**

```bash
git add scripts/check-refs.sh scripts/test-check-refs.sh .commitlintrc.json .pre-commit-config.yaml apps/web/package.json apps/web/package-lock.json
git commit -m "chore: add commitlint and check-refs pre-commit hooks (commit-msg stage)"
```

---

## Chunk 2: CI Workflow Changes

### Task 4: Trigger, concurrency, timeouts + Bandit fix + ruff pin + ESLint + npm audit

**Files:**
- Modify: `.github/workflows/ci.yml`

Fixes five existing issues (trigger, Bandit soft-fail, ruff version drift, missing ESLint, missing npm audit) plus adds concurrency cancellation and job timeouts.

- [ ] **Step 1: Change `on:` trigger to all branches**

Find:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Replace with:

```yaml
on:
  push:
    branches: ['**']
  pull_request:
    branches: [main]
```

- [ ] **Step 2: Add concurrency group**

After the `permissions:` block, add:

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

- [ ] **Step 3: Add `timeout-minutes` to all existing jobs**

| Job | Add |
|---|---|
| `lint` | `timeout-minutes: 10` |
| `security-sast` | `timeout-minutes: 15` |
| `test-backend` | `timeout-minutes: 15` |
| `test-frontend` | `timeout-minutes: 15` |
| `build-scan-images` | `timeout-minutes: 20` |

Add the `timeout-minutes` line directly under the `runs-on:` line for each job.

- [ ] **Step 4: Fix ruff version pin in lint job**

Find:

```yaml
      - run: pip install ruff
```

Replace with:

```yaml
      - run: pip install ruff==0.3.3
```

- [ ] **Step 5: Add `[tool.bandit]` section to `pyproject.toml`**

`bandit -c pyproject.toml` requires a `[tool.bandit]` section. Without it, removing the fallback will break CI with a Bandit config error on every push. Add to the bottom of `pyproject.toml`:

```toml
[tool.bandit]
targets = ["apps/api"]
severity = "medium"
confidence = "medium"
skips = []
```

Verify locally:

```bash
.venv/bin/bandit -r apps/api/ -c pyproject.toml 2>&1 | tail -5
```

Expected: scan runs cleanly (no "config not found" or "no such option" error)

- [ ] **Step 6: Fix Bandit soft-fail in security-sast job**

Find:

```yaml
      - name: Run Bandit (SAST)
        run: bandit -r apps/api/ -c pyproject.toml || bandit -r apps/api/ -ll
```

Replace with:

```yaml
      - name: Run Bandit (SAST)
        run: bandit -r apps/api/ -c pyproject.toml
```

No fallback. Safe now that `[tool.bandit]` exists.

- [ ] **Step 7: Add Node setup + ESLint + npm audit to lint job**

The `lint` job currently only has Python setup. Two separate edits are required — apply both before validating:

**Edit A — Add Node steps to the `lint` job** (after the `Run Ruff Formatter` step):

```yaml
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: apps/web/package-lock.json
      - name: Install Node dependencies
        run: cd apps/web && npm ci
      - name: Run ESLint
        run: cd apps/web && npm run lint
      - name: Run npm audit
        run: cd apps/web && npm audit --audit-level=high
```

**Edit B — Add `needs: [lint]` to `test-frontend`** (it currently has no `needs:`):

```yaml
  test-frontend:
    name: Frontend Tests & Type Check
    runs-on: ubuntu-latest
    needs: [lint]
    timeout-minutes: 15
```

Both edits are required. Apply Edit A, then Edit B, then validate.

- [ ] **Step 8: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"
```

Expected: `valid`

- [ ] **Step 9: Commit (include pyproject.toml)**

```bash
git add .github/workflows/ci.yml pyproject.toml
git commit -m "chore: fix CI trigger, concurrency, timeouts, Bandit hard-fail, ruff pin, ESLint, npm audit"
```

---

### Task 5: Coverage thresholds + next build + coverage deps

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `requirements.txt`
- Modify: `apps/web/package.json`
- Modify: `apps/web/vitest.config.ts`

Adds `pytest-cov` for backend coverage enforcement, `@vitest/coverage-v8` + vitest.config.ts update for frontend coverage (threshold lives in config, not CLI), and `next build` to the frontend job.

**⚠️ Pre-flight check (do this BEFORE any file edits):**

Verify that `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are set as GitHub repository secrets (Settings → Secrets and variables → Actions). Without these, the `next build` step will fail CI on every push. If they are not set, add them now before proceeding.

- [ ] **Step 1: Install and pin pytest-cov in requirements.txt**

Add to `requirements.txt`:

```
pytest-cov==6.0.0
```

Install locally:

```bash
.venv/bin/pip install pytest-cov==6.0.0
```

- [ ] **Step 2: Measure current backend coverage**

```bash
.venv/bin/python -m pytest apps/ packages/ --cov=apps --cov=packages --cov-report=term-missing -q 2>&1 | tail -5
```

Note the total line coverage percentage. If below 60%, use `(actual - 5)` as the `--cov-fail-under` value in Step 5 instead of 60.

- [ ] **Step 3: Install @vitest/coverage-v8**

```bash
cd apps/web && npm install --save-dev @vitest/coverage-v8
```

Verify:

```bash
grep "coverage-v8" apps/web/package.json
```

Expected: `"@vitest/coverage-v8": "^..."`

- [ ] **Step 4: Measure current frontend coverage**

```bash
cd apps/web && npx vitest run --coverage --reporter=verbose 2>&1 | tail -10
```

Note the lines coverage percentage. If below 60%, adjust `thresholds.lines` in Step 5b to `(actual - 5)`.

- [ ] **Step 5a: Update test-backend job to enforce coverage**

Find in `test-backend`:

```yaml
      - name: Run pytest
        run: python -m pytest apps/ packages/ -v --tb=short
```

Replace with:

```yaml
      - name: Run pytest with coverage
        run: python -m pytest apps/ packages/ -v --tb=short --cov=apps --cov=packages --cov-report=term-missing --cov-fail-under=60
```

(Adjust `60` based on measurement in Step 2 if needed.)

**Important:** This and the `requirements.txt` change in Step 1 must be committed together — the CI job installs from `requirements.txt`, so `pytest-cov` must be in that file before `--cov` flags are used.

- [ ] **Step 5b: Add coverage threshold to `apps/web/vitest.config.ts`**

Vitest coverage thresholds cannot be passed as CLI flags — they must be in the config. The current `vitest.config.ts` has a `test:` block but no `coverage:` block.

In `apps/web/vitest.config.ts`, add a `coverage` property inside the `defineConfig` object, alongside the `test:` block:

```typescript
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./setupTests.ts'],
    globals: true,
    exclude: ['**/node_modules/**', '**/e2e/**', '**/*.spec.ts'],
    alias: {
      '@': path.resolve(__dirname, './'),
    },
    coverage: {
      provider: 'v8',
      thresholds: {
        lines: 60,
      },
    },
  },
});
```

(Adjust `60` based on measurement in Step 4 if needed.)

- [ ] **Step 6: Update test-frontend job — add coverage + next build**

In `test-frontend`, find:

```yaml
      - name: Run Vitest
        run: cd apps/web && npm test -- --passWithNoTests
```

Replace with:

```yaml
      - name: Run Vitest with coverage
        run: cd apps/web && npx vitest run --coverage --passWithNoTests
      - name: Build Next.js
        run: cd apps/web && npm run build
        env:
          NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}
          NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY }}
```

Note: `--coverage` alone is sufficient — the threshold is enforced by `vitest.config.ts`.

- [ ] **Step 7: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"
```

- [ ] **Step 8: Commit (all four files together)**

`requirements.txt` and `ci.yml` must be in the same commit — CI will fail if `pytest-cov` is missing from requirements.txt when `--cov` flags are present.

```bash
git add .github/workflows/ci.yml requirements.txt apps/web/package.json apps/web/package-lock.json apps/web/vitest.config.ts
git commit -m "chore: add pytest-cov and vitest coverage thresholds, add next build to CI"
```

---

### Task 6: CodeQL + dependency-review jobs

**Files:**
- Modify: `.github/workflows/ci.yml`

Adds CodeQL (auto-detects TypeScript + Python, posts results to Security tab) and dependency-review (blocks PRs that introduce high/critical CVEs).

- [ ] **Step 1: Add CodeQL job after the `security-sast` job**

```yaml
  codeql:
    name: CodeQL Analysis
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      actions: read
      contents: read
      security-events: write
    strategy:
      fail-fast: false
      matrix:
        language: [javascript-typescript, python]
    steps:
      - uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{ matrix.language }}

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
        with:
          category: "/language:${{ matrix.language }}"
```

Note: `permissions.security-events: write` is required to upload results to the Security tab. The top-level `permissions: contents: read` is overridden at the job level.

- [ ] **Step 2: Add dependency-review job after `codeql`**

```yaml
  dependency-review:
    name: Dependency Review
    runs-on: ubuntu-latest
    timeout-minutes: 5
    if: github.event_name == 'pull_request'
    permissions:
      contents: read
      pull-requests: read
    steps:
      - uses: actions/checkout@v4

      - name: Dependency Review
        uses: actions/dependency-review-action@v4
        with:
          fail-on-severity: high
```

This job only runs on `pull_request` events (not on plain `push`). It does NOT gate `build-push-images` — it's a PR-only advisory check.

- [ ] **Step 3: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: add CodeQL SAST and dependency-review jobs to CI"
```

---

### Task 7: Playwright E2E job + playwright.config.ts timeout

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `apps/web/playwright.config.ts`

Adds the `test-e2e` job. Playwright's `webServer` block (already in `playwright.config.ts`) auto-starts `npm run dev` in CI, so no deployed environment is needed. The 120s timeout prevents false failures on cold Next.js starts.

- [ ] **Step 1: Add `timeout: 120_000` to webServer in playwright.config.ts**

In `apps/web/playwright.config.ts`, find:

```typescript
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
```

Replace with:

```typescript
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
```

- [ ] **Step 2: Run E2E tests locally to confirm they pass**

```bash
cd apps/web && npx playwright test --project=chromium 2>&1 | tail -15
```

Expected: `e2e/auth.spec.ts` passes. If Playwright browsers not installed:

```bash
cd apps/web && npx playwright install chromium && npx playwright test --project=chromium
```

- [ ] **Step 3: Add test-e2e job to ci.yml (after test-frontend)**

```yaml
  test-e2e:
    name: Playwright E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 15
    needs: [lint]
    defaults:
      run:
        working-directory: apps/web
    env:
      NEXT_PUBLIC_SUPABASE_URL: ${{ secrets.NEXT_PUBLIC_SUPABASE_URL }}
      NEXT_PUBLIC_SUPABASE_ANON_KEY: ${{ secrets.NEXT_PUBLIC_SUPABASE_ANON_KEY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "npm"
          cache-dependency-path: apps/web/package-lock.json
      - name: Install dependencies
        run: npm ci
      - name: Install Playwright browsers
        run: npx playwright install --with-deps chromium
      - name: Run Playwright tests
        run: npx playwright test
```

Notes:
- `defaults.run.working-directory: apps/web` — all `run:` steps execute from `apps/web/`. The `uses:` actions (checkout, setup-node) are unaffected.
- The `env:` block is at job level so the Next.js dev server spawned by `webServer` inherits these vars automatically.
- This job gates `build-push-images` (added to `needs:` in Task 8).

- [ ] **Step 4: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/ci.yml apps/web/playwright.config.ts
git commit -m "chore: add Playwright E2E job to CI and increase webServer timeout to 120s"
```

---

## Chunk 3: Docker/GHCR + Dependabot + Docs

### Task 8: Rename build-scan-images → build-push-images + GHCR push

**Files:**
- Modify: `.github/workflows/ci.yml`

Renames the job, adds GHCR login + SHA-tagged push (main branch only), removes `latest` tag, updates `needs:` to gate on all test + security jobs.

- [ ] **Step 1: Replace the entire `build-scan-images` job**

Delete the existing `build-scan-images` job and replace it with:

```yaml
  build-push-images:
    name: Build, Scan & Push Images
    runs-on: ubuntu-latest
    timeout-minutes: 20
    needs: [test-backend, test-frontend, test-e2e, security-sast, codeql]
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build API Image (local for scan)
        uses: docker/build-push-action@v5
        with:
          context: .
          target: api
          load: true
          push: false
          tags: scale-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Run Trivy vulnerability scanner on API image
        # BUG-009 fix: Pinned to immutable SHA (v0.29.0 — 2026-03)
        uses: aquasecurity/trivy-action@18f2510ee396bbf400402947b394f2dd8c87dbb0
        with:
          image-ref: 'scale-api:${{ github.sha }}'
          format: 'table'
          exit-code: '1'
          ignore-unfixed: true
          vuln-type: 'os,library'
          severity: 'CRITICAL,HIGH'

      - name: Log in to GHCR
        if: github.ref == 'refs/heads/main'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Push to GHCR
        if: github.ref == 'refs/heads/main'
        run: |
          docker tag scale-api:${{ github.sha }} ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.sha }}
          docker push ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.sha }}
```

Key design points:
- `push: false` — build locally first so Trivy can scan without registry credentials
- No `latest` tag anywhere in the file
- `if: github.ref == 'refs/heads/main'` — login and push only on main (not feature branches)
- `packages: write` at job level (overrides top-level `contents: read`)

- [ ] **Step 2: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('valid')"
```

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: rename build-scan-images to build-push-images, push SHA-tagged images to GHCR on main"
```

---

### Task 9: dependabot.yml

**Files:**
- Create: `.github/dependabot.yml`

- [ ] **Step 1: Create `.github/dependabot.yml`**

```yaml
version: 2
updates:
  - package-ecosystem: "npm"
    directory: "/apps/web"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "javascript"

  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "python"

  - package-ecosystem: "github-actions"
    directory: "/.github/workflows"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "github-actions"
```

- [ ] **Step 2: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml')); print('valid')"
```

- [ ] **Step 3: Commit**

```bash
git add .github/dependabot.yml
git commit -m "chore: add dependabot.yml for weekly npm, pip, and github-actions auto-PRs"
```

---

### Task 10: HLD sync + LLD 006 status update

**Files:**
- Modify: `docs/design/system-architecture.md`
- Modify: `docs/features/006-ci-cd-pipeline-hardening.md`

- [ ] **Step 1: Read `docs/design/system-architecture.md` before editing**

```bash
# Confirm the Infra subgraph location and changelog format
grep -n "subgraph Infra\|## Changelog\|Date.*Feature\|GHCR" docs/design/system-architecture.md
```

Expected: Infra subgraph around line 36, Changelog section around line 161, no GHCR line yet.

- [ ] **Step 2: Add GHCR node to the Infrastructure subgraph**

Find the `Infra` subgraph (exact text):

```
    subgraph Infra["🗄️ Infrastructure"]
        DB["💾 Supabase<br/>(Postgres + RLS)"]
        Redis["⚡ Upstash Redis<br/>(Cache + Queue)"]
        Worker["⚙️ Celery Worker<br/>(Async Tasks)"]
    end
```

Replace with:

```
    subgraph Infra["🗄️ Infrastructure"]
        DB["💾 Supabase<br/>(Postgres + RLS)"]
        Redis["⚡ Upstash Redis<br/>(Cache + Queue)"]
        Worker["⚙️ Celery Worker<br/>(Async Tasks)"]
        GHCR["📦 GHCR<br/>(Container Registry)"]
    end
```

- [ ] **Step 3: Add Changelog entry to system-architecture.md**

The existing Changelog table has three columns: `| Date | Feature | Change |`. Add this row:

```
| 2026-03-23 | CI/CD Hardening (LLD 006) | Added GHCR container registry to Infrastructure. CI pushes scale-api:<sha> to GHCR on every main branch push. Refs: docs/features/006-ci-cd-pipeline-hardening.md |
```

- [ ] **Step 4: Update LLD 006 status**

In `docs/features/006-ci-cd-pipeline-hardening.md`:
- Change `Status: Draft` → `Status: Implemented`
- Add to the Changelog table:

```
| 2026-03-23 | Implementation complete. All 21 success criteria implemented. Status → Implemented. |
```

- [ ] **Step 5: Run full local verification suite (covers all LLD criteria verifiable locally)**

```bash
# 1. Bandit runs with pyproject.toml (no fallback)
.venv/bin/bandit -r apps/api/ -c pyproject.toml 2>&1 | tail -3

# 2. npm audit passes
cd apps/web && npm audit --audit-level=high; cd -

# 3. ESLint passes
cd apps/web && npm run lint; cd -

# 4. next build (requires env vars) — skip if secrets not available locally
# cd apps/web && NEXT_PUBLIC_SUPABASE_URL=https://x.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=dummy npm run build; cd -

# 5. Backend coverage (≥60% or adjusted floor)
.venv/bin/python -m pytest apps/ packages/ -q --cov=apps --cov=packages --cov-fail-under=60 2>&1 | tail -5

# 6. Frontend coverage (≥60% or adjusted floor)
cd apps/web && npx vitest run --coverage 2>&1 | tail -5; cd -

# 7. Pre-commit all hooks (detect-private-key, detect-aws-credentials, tsc, prettier, ruff)
pre-commit run --all-files

# 8. commitlint + check-refs hooks are installed
ls .git/hooks/pre-commit .git/hooks/commit-msg

# 9. check-refs.sh test suite
bash scripts/test-check-refs.sh

# 10. Ruff version matches
.venv/bin/pip show ruff | grep Version
grep "ruff==" .github/workflows/ci.yml
# Both should show 0.3.3

# 11. CI YAML valid
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('ci.yml: valid')"
python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml')); print('dependabot.yml: valid')"

# 12. Job timeouts present in ci.yml
grep "timeout-minutes" .github/workflows/ci.yml | wc -l
# Expected: at least 7 lines (one per job)
```

All expected to pass.

- [ ] **Step 6: Commit docs**

```bash
git add docs/design/system-architecture.md docs/features/006-ci-cd-pipeline-hardening.md
git commit -m "docs: sync system-architecture HLD with GHCR, update LLD 006 status to Implemented

Refs: docs/features/006-ci-cd-pipeline-hardening.md"
```

---

## Post-Implementation Verification (after pushing to GitHub)

**Local verification (Task 10 Step 5) must pass before pushing.**

Push to a feature branch and open a PR to `main`. Verify all 21 LLD success criteria:

| # | LLD Criterion | Verified by | Expected |
|---|---|---|---|
| 1 | Bandit hard-fail | Task 10 Step 5 (local) | Bandit exits cleanly with `[tool.bandit]` |
| 2 | npm audit | Task 10 Step 5 (local) | Exit 0, no high/critical CVEs |
| 3 | ESLint in CI | `lint` job logs | ESLint step passes |
| 4 | next build in CI | `test-frontend` job logs | Build step passes |
| 5 | GHCR SHA push | GitHub → Packages tab (after main merge) | `scale-api:<sha>` visible |
| 6 | No `latest` tag | GitHub → Packages tab | Only SHA tags, no `latest` |
| 7 | CI on all branches | GitHub Actions | Run appears for feature branch push |
| 8 | CodeQL SAST | Security → Code Scanning | Results appear (0 or more findings) |
| 9 | Backend coverage ≥60% | `test-backend` job logs | Coverage threshold passed |
| 10 | Frontend coverage ≥60% | `test-frontend` job logs | Vitest threshold passed |
| 11 | Concurrency cancel | GitHub Actions | Push twice → first run Cancelled |
| 12 | detect-private-key active | Task 10 Step 5 (pre-commit) | Hook runs and passes |
| 13 | tsc in pre-commit | Task 10 Step 5 (pre-commit) | frontend-typecheck hook passes |
| 14 | Prettier in pre-commit | Task 10 Step 5 (pre-commit) | prettier-check hook passes |
| 15 | commitlint active | `.git/hooks/commit-msg` exists | File present after `pre-commit install --hook-type commit-msg` |
| 16 | check-refs.sh active | Task 10 Step 5 (test suite) | 9/9 pass |
| 17 | ruff version match | Task 10 Step 5 (grep) | Both show `0.3.3` |
| 18 | Job timeouts | Task 10 Step 5 (grep) | ≥7 `timeout-minutes` lines in ci.yml |
| 19 | dependabot.yml | GitHub → Insights → Dependency graph | Dependabot enabled; PRs appear after ~1 week |
| 20 | dependency-review | PR checks | Job appears for PRs to main |
| 21 | Playwright E2E | `test-e2e` job logs | `e2e/auth.spec.ts` passes |

**Manual setup required before merging:**
- Add `NEXT_PUBLIC_SUPABASE_URL` to GitHub repo secrets
- Add `NEXT_PUBLIC_SUPABASE_ANON_KEY` to GitHub repo secrets
- (Without these, `test-frontend` and `test-e2e` will fail on `next build` and `next dev`)
