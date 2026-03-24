# CI/CD Pipeline Hardening — Bug Fixes & Enhancements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 confirmed bugs in the CI/CD pipeline and deliver 2 targeted enhancements, then document the full pipeline in an architecture HLD.

**Architecture:** Bugs are targeted edits to `.github/workflows/ci.yml` and `.github/workflows/deploy.yml`. Each bug requires a committed BUG-NNN doc before its fix is implemented (Documentation Gate). Enhancements are additions to existing workflows with changelog entries in LLD 006/007. The architecture doc is a new HLD at `docs/design/ci-cd-pipeline.md`.

**Tech Stack:** GitHub Actions, Docker/GHCR, Railway, cosign (Sigstore), Vitest, Trivy, Dependabot

---

## File Map

| File | Action | Reason |
|---|---|---|
| `docs/bugs/BUG-014-trivy-cache-run-id.md` | CREATE | Bug report — Trivy cache accumulation |
| `docs/bugs/BUG-015-vitest-pass-with-no-tests.md` | CREATE | Bug report — `--passWithNoTests` silences empty suite |
| `docs/bugs/BUG-016-concurrency-cancels-docker-push.md` | CREATE | Bug report — cancel-in-progress on main |
| `docs/bugs/BUG-017-cosign-signature-never-verified.md` | CREATE | Bug report — unsigned images can deploy |
| `.github/workflows/ci.yml` | MODIFY | Fix BUG-014, BUG-015, BUG-016 |
| `.github/workflows/deploy.yml` | MODIFY | Fix BUG-017; add smoke diagnostics + staging auto-rollback |
| `docs/features/006-ci-cd-pipeline-hardening.md` | MODIFY | Changelog for CI enhancements |
| `docs/features/007-cd-implementation.md` | MODIFY | Changelog for CD enhancements |
| `docs/design/ci-cd-pipeline.md` | CREATE | New HLD — full pipeline architecture |

---

## Phase 1 — Bug Reports (must precede all code changes)

### Task 1: Create BUG-014 — Trivy cache run_id accumulation

**Files:**
- Create: `docs/bugs/BUG-014-trivy-cache-run-id.md`

**Context:** In `ci.yml` the Trivy cache key is `trivy-db-${{ github.run_id }}`. Since `run_id` is unique per run, the exact key never matches — a new entry is written every run while old entries pile up, consuming the 10 GB repo cache budget.

- [ ] **Step 1: Get the next doc number**

```bash
bash .claude/skills/design-docs/scripts/next_doc_number.sh bugs
# Expected: BUG-014
```

- [ ] **Step 2: Create BUG-014 via design-docs skill**

Content to include:
- **Severity:** Low
- **Component:** `.github/workflows/ci.yml` — `Cache Trivy DB` step
- **Symptom:** One new GitHub Actions cache entry is created per CI run; old entries never expire naturally; 10 GB repo cache budget consumed without bound
- **Root Cause:** `key: trivy-db-${{ github.run_id }}` — `run_id` is unique, so exact key never hits; `actions/cache` always writes a new entry. `restore-keys: trivy-db-` does produce a prefix-match hit, so the DB IS restored — but the unbounded write behaviour is the defect.
- **Fix:** Replace the `run_id` key with a weekly date stamp so cache entries are reused within a week, then naturally replaced when a new week starts:

  ```yaml
  key: trivy-db-${{ runner.os }}-${{ steps.date.outputs.week }}
  restore-keys: trivy-db-${{ runner.os }}-
  ```

  Add a preceding step to compute the week:

  ```yaml
  - name: Get week stamp for cache key
    id: date
    run: echo "week=$(date +%Y-%U)" >> $GITHUB_OUTPUT
  ```

- [ ] **Step 3: Run spec review**

```
Skill: superpowers:code-reviewer
```

- [ ] **Step 4: Fix review issues, then commit**

```bash
git add docs/bugs/BUG-014-trivy-cache-run-id.md
git commit -m "docs: add BUG-014 — Trivy cache run_id accumulation"
```

---

### Task 2: Create BUG-015 — vitest `--passWithNoTests` silences empty suite

**Files:**
- Create: `docs/bugs/BUG-015-vitest-pass-with-no-tests.md`

**Context:** In `ci.yml` line 113–114:

```yaml
run: cd apps/web && npx vitest run --coverage --passWithNoTests
```

`vitest.config.ts` already enforces `coverage.thresholds.lines: 60` — that gate works correctly when tests exist. The defect is `--passWithNoTests`: if all test files are accidentally excluded (wrong glob, deleted suite, mis-scoped exclude), vitest exits 0 with no output. CI stays green while the entire test suite has silently disappeared.

- [ ] **Step 1: Create BUG-015 via design-docs skill**

Content:
- **Severity:** Medium
- **Component:** `.github/workflows/ci.yml` — `Run Vitest with coverage` step
- **Symptom:** CI passes with exit 0 when no test files match — an empty test suite is indistinguishable from a passing one
- **Root Cause:** `--passWithNoTests` flag suppresses the "no tests found" error. Note: the `lines: 60` threshold in `vitest.config.ts` is NOT the problem — it correctly fails on low coverage when tests exist
- **Fix:** Remove `--passWithNoTests`. Vitest will exit 1 by default when no test files match, which is the correct behaviour. Add `--reporter=verbose` for clearer CI output.

- [ ] **Step 2: Run spec review**

```
Skill: superpowers:code-reviewer
```

- [ ] **Step 3: Fix issues and commit**

```bash
git add docs/bugs/BUG-015-vitest-pass-with-no-tests.md
git commit -m "docs: add BUG-015 — vitest --passWithNoTests silences empty test suite"
```

---

### Task 3: Create BUG-016 — Concurrency cancel-in-progress aborts Docker push on main

**Files:**
- Create: `docs/bugs/BUG-016-concurrency-cancels-docker-push.md`

**Context:** `ci.yml` lines 13–15:

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

Two commits landing on `main` in quick succession cause the first run to be cancelled — potentially mid-`docker push`. A cancelled push leaves a partial or corrupt manifest in GHCR. The deploy workflow then picks up a bad image SHA.

- [ ] **Step 1: Create BUG-016 via design-docs skill**

Content:
- **Severity:** High
- **Component:** `.github/workflows/ci.yml` — `concurrency` block
- **Symptom:** Rapid pushes to `main` can cancel an in-flight Docker push, corrupting the GHCR manifest
- **Root Cause:** `cancel-in-progress: true` is applied globally including `refs/heads/main`
- **Fix:** Restrict cancellation to PRs only — safe to cancel a PR run when a new commit arrives, but `main` pushes must always run to completion:

  ```yaml
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
  ```

- [ ] **Step 2: Run spec review**

```
Skill: superpowers:code-reviewer
```

- [ ] **Step 3: Fix and commit**

```bash
git add docs/bugs/BUG-016-concurrency-cancels-docker-push.md
git commit -m "docs: add BUG-016 — cancel-in-progress can abort Docker push on main"
```

---

### Task 4: Create BUG-017 — cosign signatures never verified before Railway deploy

**Files:**
- Create: `docs/bugs/BUG-017-cosign-signature-never-verified.md`

**Context:** `ci.yml` signs the image with cosign after push. `deploy.yml` verifies image existence via `docker manifest inspect` but never calls `cosign verify`. A token-compromised direct push to GHCR bypasses CI entirely — the image deploys unsigned without detection.

- [ ] **Step 1: Create BUG-017 via design-docs skill**

Content:
- **Severity:** High (supply chain security)
- **Component:** `.github/workflows/deploy.yml` — pre-deploy verification
- **Symptom:** Images pushed to GHCR by any means other than CI would deploy to staging and production without triggering any signature check
- **Root Cause:** No `cosign verify` step exists in `deploy.yml`; only `docker manifest inspect` (existence check) is performed
- **Fix:** Add cosign verification before the Railway deploy step in both `deploy-staging` and `deploy-production` jobs:

  ```yaml
  - name: Install cosign
    uses: sigstore/cosign-installer@v3

  - name: Verify image signature
    run: |
      cosign verify \
        --certificate-identity-regexp="https://github.com/${{ github.repository }}/.*" \
        --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
        ghcr.io/${{ github.repository_owner }}/scale-api:${{ steps.sha.outputs.value }}
  ```

  Note: `steps.sha.outputs.value` is the output of the existing `Set deploy SHA` step in both jobs.

- [ ] **Step 2: Run spec review**

```
Skill: superpowers:code-reviewer
```

- [ ] **Step 3: Fix and commit**

```bash
git add docs/bugs/BUG-017-cosign-signature-never-verified.md
git commit -m "docs: add BUG-017 — cosign signatures never verified before Railway deploy"
```

---

## Phase 2 — CI.YML Bug Fixes

### Task 5: Fix BUG-014 — Trivy cache weekly key

**Files:**
- Modify: `.github/workflows/ci.yml` — `Cache Trivy DB` step and add `Get week stamp` step before it

**Current (find this block):**

```yaml
- name: Cache Trivy DB
  uses: actions/cache@v4
  with:
    path: ~/.cache/trivy
    key: trivy-db-${{ github.run_id }}
    restore-keys: trivy-db-
```

**Replace with:**

```yaml
- name: Get week stamp for Trivy cache key
  id: date
  run: echo "week=$(date +%Y-%U)" >> $GITHUB_OUTPUT

- name: Cache Trivy DB
  uses: actions/cache@v4
  with:
    path: ~/.cache/trivy
    key: trivy-db-${{ runner.os }}-${{ steps.date.outputs.week }}
    restore-keys: trivy-db-${{ runner.os }}-
```

- [ ] **Step 1: Apply the edit**

- [ ] **Step 2: Verify YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML valid"
```

- [ ] **Step 3: Update BUG-014 status to Implemented**
Edit `docs/bugs/BUG-014-trivy-cache-run-id.md` — set `Status: Implemented`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml docs/bugs/BUG-014-trivy-cache-run-id.md
git commit -m "fix: use weekly cache key for Trivy DB to prevent unbounded cache accumulation

Refs: docs/bugs/BUG-014-trivy-cache-run-id.md"
```

---

### Task 6: Fix BUG-015 — Remove `--passWithNoTests` from vitest command

**Files:**
- Modify: `.github/workflows/ci.yml` — `Run Vitest with coverage` step

**Current:**

```yaml
- name: Run Vitest with coverage
  run: cd apps/web && npx vitest run --coverage --passWithNoTests
```

**Target:**

```yaml
- name: Run Vitest with coverage
  run: cd apps/web && npx vitest run --coverage --reporter=verbose
```

Note: `vitest.config.ts` already has `coverage.thresholds.lines: 60` — do NOT modify it.

- [ ] **Step 1: Apply the edit**

- [ ] **Step 2: Run tests locally to verify the suite still passes**

```bash
cd apps/web && npx vitest run --coverage --reporter=verbose
# Expected: PASS, with coverage output showing lines >= 60%
```

If this exits 1 with "no test files found", there is a test configuration issue in `apps/web` that must be fixed before proceeding. Check `vitest.config.ts` include/exclude globs.

- [ ] **Step 3: Update BUG-015 status to Implemented**

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml docs/bugs/BUG-015-vitest-pass-with-no-tests.md
git commit -m "fix: remove --passWithNoTests from vitest so empty test suite fails CI

Refs: docs/bugs/BUG-015-vitest-pass-with-no-tests.md"
```

---

### Task 7: Fix BUG-016 — Disable cancel-in-progress on main

**Files:**
- Modify: `.github/workflows/ci.yml` — `concurrency` block (near top of file)

**Current:**

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

**Target:**

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}
```

- [ ] **Step 1: Apply the edit**

- [ ] **Step 2: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML valid"
```

- [ ] **Step 3: Update BUG-016 status to Implemented**

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml docs/bugs/BUG-016-concurrency-cancels-docker-push.md
git commit -m "fix: disable cancel-in-progress on main branch to protect Docker push

Refs: docs/bugs/BUG-016-concurrency-cancels-docker-push.md"
```

---

## Phase 3 — DEPLOY.YML: Bug Fix + Enhancements

### Task 8: Fix BUG-017 — Add cosign verify before Railway deploy

**Files:**
- Modify: `.github/workflows/deploy.yml`

**Two insertion points:**

**1. In `deploy-staging` job** — insert after the `docker manifest inspect` step (~line 95) and before the `Deploy to Railway (staging)` step (~line 97):

```yaml
      - name: Install cosign
        uses: sigstore/cosign-installer@v3

      - name: Verify image signature (staging)
        run: |
          cosign verify \
            --certificate-identity-regexp="https://github.com/${{ github.repository }}/.*" \
            --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
            ghcr.io/${{ github.repository_owner }}/scale-api:${{ steps.sha.outputs.value }}
```

**2. In `deploy-production` job** — the production job has no `manifest inspect` step. Insert after the `Set deploy SHA` step (~line 177) and before `Deploy to Railway (production)` (~line 193):

```yaml
      - name: Install cosign
        uses: sigstore/cosign-installer@v3

      - name: Verify image signature (production)
        run: |
          cosign verify \
            --certificate-identity-regexp="https://github.com/${{ github.repository }}/.*" \
            --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
            ghcr.io/${{ github.repository_owner }}/scale-api:${{ steps.sha.outputs.value }}
```

In both cases `steps.sha.outputs.value` is the SHA output by the `Set deploy SHA` step that already exists in each job.

- [ ] **Step 1: Read deploy.yml lines 65–200 to locate exact positions**

```bash
sed -n '65,200p' .github/workflows/deploy.yml
```

- [ ] **Step 2: Add cosign steps to deploy-staging job**

- [ ] **Step 3: Add cosign steps to deploy-production job**

- [ ] **Step 4: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo "YAML valid"
```

- [ ] **Step 5: Update BUG-017 status to Implemented**

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/deploy.yml docs/bugs/BUG-017-cosign-signature-never-verified.md
git commit -m "fix: verify cosign signature before staging and production Railway deploy

Refs: docs/bugs/BUG-017-cosign-signature-never-verified.md"
```

---

### Task 9: Enhancement — Smoke test diagnostics

**Files:**
- Modify: `.github/workflows/deploy.yml` — all 3 smoke test loops (staging ~line 150, production ~line 246, rollback ~line 325)

**Context:** Current loops only log the HTTP status code. On 360s timeout, there is no response body or verbose output to diagnose the failure.

**Pattern to apply to each loop** (replace the body of each `for` loop):

```bash
URL="<the existing vars expression for this loop>"
for i in $(seq 1 36); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$URL/health" || echo "000")
  BODY=$(curl -s --max-time 5 "$URL/health" 2>/dev/null || true)
  if [ "$STATUS" = "200" ]; then
    echo "Health check passed on attempt $i"
    exit 0
  fi
  echo "Attempt $i: HTTP $STATUS — body: $BODY — waiting 10s"
  sleep 10
done
echo "=== FINAL DIAGNOSTIC ==="
curl -v --max-time 15 "$URL/health" 2>&1 || true
echo "Health check failed after 360s"
exit 1
```

Replace `<the existing vars expression>` with:
- Staging loop: `${{ vars.STAGING_API_URL }}`
- Production loop: `${{ vars.PRODUCTION_API_URL }}`
- Rollback loop: `${{ vars.PRODUCTION_API_URL }}`

- [ ] **Step 1: Read the three loop sections**

```bash
sed -n '145,170p' .github/workflows/deploy.yml
sed -n '240,265p' .github/workflows/deploy.yml
sed -n '318,340p' .github/workflows/deploy.yml
```

- [ ] **Step 2: Apply the pattern to the staging smoke test loop**

- [ ] **Step 3: Apply the pattern to the production smoke test loop**

- [ ] **Step 4: Apply the pattern to the rollback health check loop**

- [ ] **Step 5: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo "YAML valid"
```

- [ ] **Step 6: Add changelog entry to LLD 007**

Append to `docs/features/007-cd-implementation.md` changelog:

```
| 2026-03-24 | ENHANCEMENT: Smoke test loops now log response body on each attempt and dump `curl -v` on final failure for faster post-deploy debugging |
```

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/deploy.yml docs/features/007-cd-implementation.md
git commit -m "feat: add smoke test diagnostics — response body and curl -v on final failure

Refs: docs/features/007-cd-implementation.md"
```

---

### Task 10: Enhancement — Auto-rollback staging on smoke test failure

**Files:**
- Modify: `.github/workflows/deploy.yml` — `deploy-staging` job

**Context:** Currently a staging smoke test failure leaves the service broken until a human manually triggers the rollback job. This adds automatic rollback triggered by `if: failure()` on the smoke test step.

**Approach:**
1. Before staging deploy, query Railway's API to get the currently deployed image reference (the "previous" image to roll back to)
2. Store it as a step output
3. If the staging smoke test fails, re-deploy that previous image using the same pattern as the existing rollback job (`serviceInstanceUpdate` + `serviceInstanceDeploy`)

**Step A — add before the `Deploy to Railway (staging)` step:**

```yaml
      - name: Capture previous staging SHA for rollback
        id: prev
        run: |
          python3 - <<'EOF'
          import urllib.request, json, os
          token = os.environ['RAILWAY_TOKEN']
          service_id = os.environ['RAILWAY_API_SERVICE_ID']
          env_id = os.environ['RAILWAY_STAGING_ENV_ID']
          query = json.dumps({'query': '''
          query { deployments(
            serviceId: "%s", environmentId: "%s", first: 2
          ) { edges { node { staticUrl } } } }
          ''' % (service_id, env_id)})
          req = urllib.request.Request(
              'https://backboard.railway.com/graphql/v2',
              data=query.encode(),
              headers={'Authorization': f'Bearer {token}',
                       'Content-Type': 'application/json',
                       'User-Agent': 'railway-cli/3.0.0'}
          )
          resp = json.loads(urllib.request.urlopen(req).read())
          deployments = resp.get('data', {}).get('deployments', {}).get('edges', [])
          if len(deployments) >= 2:
              prev_url = deployments[1]['node'].get('staticUrl', '')
              print(f"Previous deployment found: {prev_url}")
              with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                  f.write(f"prev_url={prev_url}\n")
          else:
              print("No previous deployment found — rollback will be skipped")
              with open(os.environ['GITHUB_OUTPUT'], 'a') as f:
                  f.write("prev_url=\n")
          EOF
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          RAILWAY_API_SERVICE_ID: ${{ vars.RAILWAY_API_SERVICE_ID }}
          RAILWAY_STAGING_ENV_ID: ${{ vars.RAILWAY_STAGING_ENV_ID }}
```

**Step B — add after the staging smoke test step (with `if: failure()`):**

```yaml
      - name: Auto-rollback staging on smoke failure
        if: failure() && steps.prev.outputs.prev_url != ''
        run: |
          python3 - <<'EOF'
          import urllib.request, json, os, sys
          token = os.environ['RAILWAY_TOKEN']
          # Rollback API service
          for service_id, env_id in [
              (os.environ['RAILWAY_API_SERVICE_ID'], os.environ['RAILWAY_STAGING_ENV_ID']),
              (os.environ['RAILWAY_WORKER_SERVICE_ID'], os.environ['RAILWAY_STAGING_ENV_ID']),
          ]:
              prev_image = os.environ['PREV_IMAGE']
              if not prev_image:
                  print(f"No previous image for {service_id} — skipping")
                  continue
              update_q = json.dumps({'query': '''
              mutation { serviceInstanceUpdate(
                  serviceId: "%s", environmentId: "%s",
                  input: { source: { image: "%s" } }
              ) }
              ''' % (service_id, env_id, prev_image)})
              req = urllib.request.Request(
                  'https://backboard.railway.com/graphql/v2',
                  data=update_q.encode(),
                  headers={'Authorization': f'Bearer {token}',
                           'Content-Type': 'application/json',
                           'User-Agent': 'railway-cli/3.0.0'}
              )
              urllib.request.urlopen(req)
              deploy_q = json.dumps({'query': '''
              mutation { serviceInstanceDeploy(
                  serviceId: "%s", environmentId: "%s"
              ) }
              ''' % (service_id, env_id)})
              req2 = urllib.request.Request(
                  'https://backboard.railway.com/graphql/v2',
                  data=deploy_q.encode(),
                  headers={'Authorization': f'Bearer {token}',
                           'Content-Type': 'application/json',
                           'User-Agent': 'railway-cli/3.0.0'}
              )
              urllib.request.urlopen(req2)
              print(f"Auto-rollback triggered for service {service_id}")
          EOF
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          RAILWAY_API_SERVICE_ID: ${{ vars.RAILWAY_API_SERVICE_ID }}
          RAILWAY_WORKER_SERVICE_ID: ${{ vars.RAILWAY_WORKER_SERVICE_ID }}
          RAILWAY_STAGING_ENV_ID: ${{ vars.RAILWAY_STAGING_ENV_ID }}
          PREV_IMAGE: ${{ steps.prev.outputs.prev_url }}
```

Note: Production auto-rollback is intentionally excluded — production rollback must remain a human decision.

- [ ] **Step 1: Read the deploy-staging job section**

```bash
sed -n '65,165p' .github/workflows/deploy.yml
```

- [ ] **Step 2: Insert the "Capture previous staging SHA" step before the existing Railway deploy step**

- [ ] **Step 3: Insert the "Auto-rollback staging" step after the staging smoke test step, using `if: failure()`**

- [ ] **Step 4: Validate YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo "YAML valid"
```

- [ ] **Step 5: Add changelog entry to LLD 007**

Append to `docs/features/007-cd-implementation.md` changelog:

```
| 2026-03-24 | ENHANCEMENT: Staging auto-rollback on smoke test failure — captures previous deployment before deploy, triggers serviceInstanceUpdate + serviceInstanceDeploy for both API and Worker services. Production rollback remains manual. |
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/deploy.yml docs/features/007-cd-implementation.md
git commit -m "feat: auto-rollback staging deployment on smoke test failure

Refs: docs/features/007-cd-implementation.md"
```

---

## Phase 4 — Architecture Documentation

### Task 11: Create CI/CD Pipeline Architecture HLD

**Files:**
- Create: `docs/design/ci-cd-pipeline.md`

**Important:** Re-read `.github/workflows/ci.yml` and `.github/workflows/deploy.yml` in their final state (after Tasks 5–10 edits) before writing this doc. Do not rely on earlier reads.

**Required sections:**

1. **Overview** — one paragraph + Mermaid diagram of the full flow:

   ```
   push to main → CI (lint → test → build-push → scan → sign)
     → deploy.yml triggers → migrations → staging deploy → cosign verify
     → smoke test → [auto-rollback on failure] → manual approval
     → production deploy → cosign verify → smoke test
   ```

2. **CI Pipeline (`ci.yml`)** — all jobs with trigger conditions, what each does, key outputs

3. **CD Pipeline (`deploy.yml`)** — deploy sequence, environment gate (GitHub Environment: production), smoke tests, manual rollback job

4. **Security Controls** — cosign sign (CI) + cosign verify (deploy), Trivy scan, SBOM (Syft), Docker action SHA pins

5. **Dependency Management** — Dependabot: npm (apps/web), pip (root), github-actions (.github/workflows), schedule: weekly Monday

6. **Required Secrets & Variables** — extract from both workflow files:

```bash
grep -oE '(secrets|vars)\.[A-Z_]+' .github/workflows/ci.yml .github/workflows/deploy.yml | sort -u
```

1. **Failure Modes & Recovery**

| Failure | Automatic Response | Manual Recovery |
|---|---|---|
| CI fails on PR | Workflow exits 1, merge blocked | Fix code, repush |
| CI fails on main | Docker push doesn't happen | Fix and repush |
| Staging smoke test fails | Auto-rollback triggers for both services | Check Railway logs |
| Production smoke test fails | Workflow exits 1, alert visible in Actions | Trigger rollback job with previous SHA |

1. **Known Limitations** — Playwright runs against `npm run dev` (not production build); no DAST; no k6 load tests; no Slack/PagerDuty alerts

1. **Changelog** — first entry: `2026-03-24 | Initial HLD created`

- [ ] **Step 1: Extract all secrets and vars referenced in both workflows**

```bash
grep -oE '(secrets|vars)\.[A-Z_]+' .github/workflows/ci.yml .github/workflows/deploy.yml | sort -u
```

- [ ] **Step 2: Re-read ci.yml and deploy.yml (final state)**

- [ ] **Step 3: Write the HLD** using the design-docs skill (HLD template)

- [ ] **Step 4: Run spec review**

```
Skill: superpowers:code-reviewer
```

- [ ] **Step 5: Fix issues and commit**

```bash
git add docs/design/ci-cd-pipeline.md
git commit -m "docs: add CI/CD pipeline architecture HLD"
```

---

## Phase 5 — Verification

### Task 12: End-to-end verification

- [ ] **Step 1: Run verification skill**

```
Skill: superpowers:verification-before-completion
```

- [ ] **Step 2: Validate all YAML files one final time**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && \
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && \
echo "All YAML valid"
```

- [ ] **Step 3: Verify CI evidence after pushing to main**

After a CI run triggered by this work, confirm in GitHub Actions:
- `Cache Trivy DB`: key is `trivy-db-Linux-<year>-<week>` (not `run_id`)
- Concurrency group does NOT cancel in-progress on main
- Vitest step: no `--passWithNoTests`, shows verbose coverage output with `lines: 60` threshold
- cosign sign step runs and exits 0
- deploy-staging: cosign verify step present and passes
- deploy-production: cosign verify step present and passes

- [ ] **Step 4: Mark all BUG docs as Verified**

Set `Status: Verified` in BUG-014, BUG-015, BUG-016, BUG-017.

- [ ] **Step 5: Commit status updates**

```bash
git add docs/bugs/BUG-014-*.md docs/bugs/BUG-015-*.md docs/bugs/BUG-016-*.md docs/bugs/BUG-017-*.md
git commit -m "docs: mark BUG-014 through BUG-017 as Verified"
```

---

## Out of Scope (Deferred)

- Dependabot pre-commit ecosystem — not supported by Dependabot natively
- Slack/PagerDuty notifications on deploy failure — requires Slack webhook setup
- Production auto-rollback — must remain a human decision
- SHA pinning for GitHub's own actions (`actions/checkout`, `actions/setup-*`) — low risk, deferred
- DAST (OWASP ZAP), k6 load tests, DORA metrics tracking
- `step-security/harden-runner`
