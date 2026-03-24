# LLD 007 — CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up a full Railway CD pipeline — migrations → staging deploy → smoke test → manual approval → production deploy → smoke test — plus SBOM generation, cosign signing, and Docker action SHA pinning.

**Architecture:** GHCR image (built by CI) is deployed to Railway staging first, then production after manual approval. Both use the same image SHA. Syft generates an SBOM and cosign signs the image after each push to GHCR, all within the existing `build-push-images` job. A `workflow_dispatch` rollback job re-deploys a named SHA.

**Tech Stack:** GitHub Actions, Railway CLI (`@railway/cli`), Supabase CLI, Syft (Anchore), cosign (Sigstore), GHCR, Docker

---

## ⚠️ Manual Setup Required Before Deploy.yml Works

These must be done by a human with Railway and GitHub access. The code changes below are safe to commit first; deploys will fail gracefully until these are in place.

| Step | Where | Detail |
|---|---|---|
| Create Railway project | railway.app | Two services: `scale-api` (web), `scale-worker` (worker) |
| Add `RAILWAY_TOKEN` to GitHub Secrets | Repo Settings → Secrets | Project-scoped token from Railway dashboard |
| Add `DATABASE_URL` to GitHub Secrets | Repo Settings → Secrets | Supabase direct Postgres connection URL |
| Add `STAGING_API_URL` to GitHub Variables | Repo Settings → Variables | e.g. `https://scale-api-staging.up.railway.app` |
| Add `PRODUCTION_API_URL` to GitHub Variables | Repo Settings → Variables | e.g. `https://scale-api.up.railway.app` |
| Create GitHub Environment `staging` | Repo Settings → Environments | No protection rules required |
| Create GitHub Environment `production` | Repo Settings → Environments | Add required reviewer (yourself) |
| Set scale-worker startCommand in Railway | Railway dashboard → scale-worker → Settings | `celery -A apps.api.celery_app worker --loglevel=info --queues=training --concurrency=2` |

---

## Files Modified

| File | Change |
|---|---|
| `.github/workflows/ci.yml` | Pin two Docker action SHAs; add `id-token: write`; add SBOM + cosign after GHCR push |
| `.github/workflows/deploy.yml` | Full replacement: add `workflow_dispatch` trigger, `run-migrations`, real Railway deploy steps, smoke tests, rollback job |
| `railway.toml` | New file — scale-api and scale-worker service config (startCommand, healthcheckPath) |
| `docs/design/system-architecture.md` | Add Railway as backend runtime, SBOM/cosign in pipeline diagram, changelog entry |
| `docs/features/007-cd-implementation.md` | Status → Implemented; DEVIATION entry for `github.repository_owner` |

---

## Task 1: Pin Docker Action SHAs in ci.yml

**Files:** Modify `.github/workflows/ci.yml` lines 202–205

The two mutable version tags need pinning to immutable commit SHAs.

- SHAs resolved at planning time:
  - `docker/setup-buildx-action@v3` → `8d2750c68a42422c14e847fe6c8ac0403b4cbd6f`
  - `docker/build-push-action@v5` → `ca052bb54ab0790a636c9b5f226502c73d547a25`

- [ ] **Step 1.1: Edit ci.yml — pin setup-buildx-action**

  In `.github/workflows/ci.yml` at line 202, change:

  ```yaml
        uses: docker/setup-buildx-action@v3
  ```

  to:

  ```yaml
        uses: docker/setup-buildx-action@8d2750c68a42422c14e847fe6c8ac0403b4cbd6f  # v3
  ```

- [ ] **Step 1.2: Edit ci.yml — pin build-push-action**

  At line 205, change:

  ```yaml
        uses: docker/build-push-action@v5
  ```

  to:

  ```yaml
        uses: docker/build-push-action@ca052bb54ab0790a636c9b5f226502c73d547a25  # v5
  ```

- [ ] **Step 1.3: Verify YAML syntax**

  ```bash
  python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
  ```

  Expected: `YAML OK`

- [ ] **Step 1.4: Commit**

  ```bash
  git add .github/workflows/ci.yml
  git commit -m "chore: pin docker/setup-buildx-action and build-push-action to commit SHAs

  Refs: docs/features/007-cd-implementation.md"
  ```

---

## Task 2: Add SBOM + cosign to build-push-images

**Files:** Modify `.github/workflows/ci.yml` — `build-push-images` job (lines 190–238)

SBOM (Syft) and image signing (cosign keyless) run only on `main` after the GHCR push. cosign keyless requires `id-token: write` on the job.

**Note:** All image references use `github.repository_owner` (matching the existing `Push to GHCR` step at line 236). The spec documents `github.repository` — this is a spec error. A DEVIATION entry will be added to LLD 007 in Task 5.

- [ ] **Step 2.1: Add `id-token: write` to build-push-images permissions**

  In `.github/workflows/ci.yml`, find the `build-push-images` job permissions block (lines 195–197):

  ```yaml
      permissions:
        contents: read
        packages: write
  ```

  Replace with:

  ```yaml
      permissions:
        contents: read
        packages: write
        id-token: write  # required for cosign keyless signing (Sigstore OIDC)
  ```

- [ ] **Step 2.2: Add SBOM generation + upload + cosign steps after "Push to GHCR"**

  After the `Push to GHCR` step (the closing `|` of the run block at line 237), add:

  ```yaml

        - name: Generate SBOM
          if: github.ref == 'refs/heads/main'
          run: |
            curl -sSfL https://raw.githubusercontent.com/anchore/syft/main/install.sh | sh -s -- -b /usr/local/bin
            syft ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.sha }} -o spdx-json > sbom.json

        - name: Upload SBOM artifact
          if: github.ref == 'refs/heads/main'
          uses: actions/upload-artifact@v4
          with:
            name: sbom-${{ github.sha }}
            path: sbom.json
            retention-days: 30

        - name: Sign image with cosign
          if: github.ref == 'refs/heads/main'
          run: |
            COSIGN_VERSION=v2.4.3
            curl -sSL -o /usr/local/bin/cosign \
              "https://github.com/sigstore/cosign/releases/download/${COSIGN_VERSION}/cosign-linux-amd64"
            chmod +x /usr/local/bin/cosign
            cosign sign --yes \
              ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.sha }}
  ```

- [ ] **Step 2.3: Verify YAML syntax**

  ```bash
  python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
  ```

  Expected: `YAML OK`

- [ ] **Step 2.4: Commit**

  ```bash
  git add .github/workflows/ci.yml
  git commit -m "feat: add SBOM generation (Syft) and cosign image signing to CI

  - Syft generates SPDX JSON SBOM after each push to GHCR (30-day retention)
  - cosign signs the image keylessly via Sigstore OIDC (no key management)
  - Both steps run only on main, after the GHCR push step

  Refs: docs/features/007-cd-implementation.md"
  ```

---

## Task 3: Create railway.toml

**Files:** Create `railway.toml` at repo root

Configures scale-api (startCommand, healthcheckPath) and scale-worker (startCommand reference only — workers have no HTTP health check; Railway uses process liveness). The multi-service TOML uses `[services.<name>.deploy]` blocks.

- [ ] **Step 3.1: Create railway.toml**

  Create file `railway.toml` at repo root:

  ```toml
  # railway.toml — service deploy configuration.
  # Deployed via: railway up --service <name> --image ghcr.io/.../scale-api:<sha> --detach
  # Railway applies the matching [services.<name>.deploy] block at runtime.

  [services.scale-api.deploy]
  startCommand = "uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT --workers 1"
  healthcheckPath = "/health"
  healthcheckTimeout = 300

  [services.scale-worker.deploy]
  # Workers serve no HTTP traffic; Railway uses process liveness (exit code) for health.
  startCommand = "celery -A apps.api.celery_app worker --loglevel=info --queues=training --concurrency=2"
  ```

- [ ] **Step 3.2: Verify /health endpoint exists**

  ```bash
  grep -n '"/health"' apps/api/main.py
  ```

  Expected: line showing `@app.get("/health"` — confirmed to exist at line 252.

- [ ] **Step 3.3: Commit**

  ```bash
  git add railway.toml
  git commit -m "feat: add railway.toml for scale-api and scale-worker service configuration

  Refs: docs/features/007-cd-implementation.md"
  ```

---

## Task 4: Rewrite deploy.yml — complete pipeline (atomic)

**Files:** Modify `.github/workflows/deploy.yml` — full file replacement in one commit

Replace the two `echo "TODO"` stubs with the complete pipeline. All jobs written and committed atomically to avoid an intermediate half-wired state.

Jobs added:
- `check-ci-success` (updated: add `timeout-minutes: 5`)
- `run-migrations` (new)
- `deploy-staging` (replaces stub)
- `smoke-test-staging` (new)
- `deploy-production` (replaces stub; `needs: [smoke-test-staging, run-migrations]`)
- `smoke-test-production` (new)
- `rollback` (new; `workflow_dispatch` only)

- [ ] **Step 4.1: Write complete deploy.yml**

  Replace the entire content of `.github/workflows/deploy.yml` with:

  ```yaml
  name: Deploy

  on:
    workflow_run:
      workflows: ["CI"]
      types: [completed]
      branches: [main]
    workflow_dispatch:
      inputs:
        rollback_sha:
          description: 'Image SHA to rollback to (required)'
          required: true
          type: string

  concurrency:
    group: deploy-${{ github.ref }}
    cancel-in-progress: true

  permissions:
    contents: read

  jobs:
    check-ci-success:
      name: Check CI passed
      runs-on: ubuntu-latest
      if: github.event_name == 'workflow_run'
      timeout-minutes: 5
      steps:
        - name: Abort if CI did not succeed
          if: ${{ github.event.workflow_run.conclusion != 'success' }}
          run: |
            echo "CI workflow concluded with: ${{ github.event.workflow_run.conclusion }}"
            echo "Aborting deployment — CI must pass before deploying."
            exit 1
        - name: CI passed — proceeding
          run: echo "CI succeeded (run ${{ github.event.workflow_run.id }}). Proceeding to deploy."

    run-migrations:
      name: Run DB Migrations
      needs: [check-ci-success]
      runs-on: ubuntu-latest
      if: github.event_name == 'workflow_run'
      timeout-minutes: 10
      steps:
        - uses: actions/checkout@v4
          with:
            ref: ${{ github.event.workflow_run.head_sha }}

        - name: Install Supabase CLI
          run: npm install -g supabase

        - name: Run migrations
          env:
            DATABASE_URL: ${{ secrets.DATABASE_URL }}
          run: supabase db push --db-url "$DATABASE_URL"

    deploy-staging:
      name: Deploy to Staging
      needs: [run-migrations]
      runs-on: ubuntu-latest
      if: github.event_name == 'workflow_run'
      timeout-minutes: 10
      environment:
        name: staging
        url: ${{ vars.STAGING_API_URL }}
      permissions:
        contents: read
        packages: read
      steps:
        - name: Log in to GHCR
          uses: docker/login-action@v3
          with:
            registry: ghcr.io
            username: ${{ github.actor }}
            password: ${{ secrets.GITHUB_TOKEN }}

        - name: Verify image exists in GHCR
          run: docker manifest inspect ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.event.workflow_run.head_sha }}

        - name: Install Railway CLI
          run: npm install -g @railway/cli

        - name: Deploy scale-api to staging
          env:
            RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          run: |
            railway up --service scale-api \
              --image ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.event.workflow_run.head_sha }} \
              --detach

        - name: Deploy scale-worker to staging
          env:
            RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          run: |
            railway up --service scale-worker \
              --image ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.event.workflow_run.head_sha }} \
              --detach

    smoke-test-staging:
      name: Smoke Test Staging
      needs: [deploy-staging]
      runs-on: ubuntu-latest
      if: github.event_name == 'workflow_run'
      timeout-minutes: 5
      steps:
        - name: Wait for health
          run: |
            for i in $(seq 1 18); do
              STATUS=$(curl -s -o /dev/null -w "%{http_code}" ${{ vars.STAGING_API_URL }}/health)
              if [ "$STATUS" = "200" ]; then
                echo "Health check passed on attempt $i"
                exit 0
              fi
              echo "Attempt $i: HTTP $STATUS — waiting 10s"
              sleep 10
            done
            echo "Health check failed after 180s"
            exit 1

    deploy-production:
      name: Deploy to Production
      needs: [smoke-test-staging, run-migrations]
      runs-on: ubuntu-latest
      if: github.event_name == 'workflow_run'
      timeout-minutes: 10
      environment:
        name: production
        url: ${{ vars.PRODUCTION_API_URL }}
      permissions:
        contents: read
        packages: read
      steps:
        - name: Log in to GHCR
          uses: docker/login-action@v3
          with:
            registry: ghcr.io
            username: ${{ github.actor }}
            password: ${{ secrets.GITHUB_TOKEN }}

        - name: Install Railway CLI
          run: npm install -g @railway/cli

        - name: Deploy scale-api to production
          env:
            RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          run: |
            railway up --service scale-api \
              --image ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.event.workflow_run.head_sha }} \
              --detach

        - name: Deploy scale-worker to production
          env:
            RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          run: |
            railway up --service scale-worker \
              --image ghcr.io/${{ github.repository_owner }}/scale-api:${{ github.event.workflow_run.head_sha }} \
              --detach

    smoke-test-production:
      name: Smoke Test Production
      needs: [deploy-production]
      runs-on: ubuntu-latest
      if: github.event_name == 'workflow_run'
      timeout-minutes: 5
      steps:
        - name: Wait for health
          run: |
            for i in $(seq 1 18); do
              STATUS=$(curl -s -o /dev/null -w "%{http_code}" ${{ vars.PRODUCTION_API_URL }}/health)
              if [ "$STATUS" = "200" ]; then
                echo "Health check passed on attempt $i"
                exit 0
              fi
              echo "Attempt $i: HTTP $STATUS — waiting 10s"
              sleep 10
            done
            echo "Health check failed after 180s"
            exit 1

    rollback:
      name: Rollback Deployment
      runs-on: ubuntu-latest
      if: github.event_name == 'workflow_dispatch'
      timeout-minutes: 15
      permissions:
        contents: read
        packages: read
      steps:
        - name: Log in to GHCR
          uses: docker/login-action@v3
          with:
            registry: ghcr.io
            username: ${{ github.actor }}
            password: ${{ secrets.GITHUB_TOKEN }}

        - name: Verify rollback image exists
          run: docker manifest inspect ghcr.io/${{ github.repository_owner }}/scale-api:${{ inputs.rollback_sha }}

        - name: Install Railway CLI
          run: npm install -g @railway/cli

        - name: Rollback scale-api
          env:
            RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          run: |
            railway up --service scale-api \
              --image ghcr.io/${{ github.repository_owner }}/scale-api:${{ inputs.rollback_sha }} \
              --detach

        - name: Rollback scale-worker
          env:
            RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
          run: |
            railway up --service scale-worker \
              --image ghcr.io/${{ github.repository_owner }}/scale-api:${{ inputs.rollback_sha }} \
              --detach

        - name: Verify rollback health
          run: |
            for i in $(seq 1 18); do
              STATUS=$(curl -s -o /dev/null -w "%{http_code}" ${{ vars.PRODUCTION_API_URL }}/health)
              if [ "$STATUS" = "200" ]; then
                echo "Rollback health check passed on attempt $i"
                exit 0
              fi
              echo "Attempt $i: HTTP $STATUS — waiting 10s"
              sleep 10
            done
            echo "Rollback health check failed after 180s"
            exit 1
  ```

- [ ] **Step 4.2: Verify YAML syntax**

  ```bash
  python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))" && echo "YAML OK"
  ```

  Expected: `YAML OK`

- [ ] **Step 4.3: Verify all 7 jobs present**

  ```bash
  grep "^  [a-z].*:" .github/workflows/deploy.yml
  ```

  Expected: `check-ci-success`, `run-migrations`, `deploy-staging`, `smoke-test-staging`, `deploy-production`, `smoke-test-production`, `rollback`

- [ ] **Step 4.4: Commit**

  ```bash
  git add .github/workflows/deploy.yml
  git commit -m "feat: implement full CD pipeline in deploy.yml

  - run-migrations: supabase db push before staging deploy
  - deploy-staging: railway up for scale-api + scale-worker
  - smoke-test-staging: 18x10s health check loop
  - deploy-production: needs [smoke-test-staging, run-migrations], manual approval gate
  - smoke-test-production: same retry loop against PRODUCTION_API_URL
  - rollback: workflow_dispatch only, re-deploys a named SHA

  Refs: docs/features/007-cd-implementation.md"
  ```

---

## Task 5: Update system-architecture.md and LLD 007

**Files:** Modify `docs/design/system-architecture.md` and `docs/features/007-cd-implementation.md`

- [ ] **Step 5.1: Read current system-architecture.md**

  ```bash
  cat docs/design/system-architecture.md
  ```

- [ ] **Step 5.2: Add Railway to infra section**

  Find the infrastructure/deployment section and add a Railway entry:
  - Railway hosts `scale-api` (FastAPI, `uvicorn`, port `$PORT`) and `scale-worker` (Celery)
  - Both services use the same GHCR image (`ghcr.io/<owner>/scale-api:<sha>`) pulled by SHA on each deploy
  - Both services share one Supabase database (no separate staging DB at this stage)

- [ ] **Step 5.3: Add SBOM + cosign to CI/CD pipeline description**

  After the GHCR push step, add:
  - Syft generates SPDX JSON SBOM — uploaded as workflow artifact (30-day retention)
  - cosign signs the image keylessly via Sigstore OIDC — verifiable with `cosign verify`

- [ ] **Step 5.4: Append system-architecture.md changelog entry**

  ```
  | 2026-03-23 | Added Railway (scale-api + scale-worker), SBOM (Syft), cosign signing to pipeline. Reflects LLD 007 implementation. |
  ```

- [ ] **Step 5.5: Update LLD 007 status to Implemented**

  In `docs/features/007-cd-implementation.md`, change:

  ```
  > **Status:** Draft
  ```

  to:

  ```
  > **Status:** Implemented
  ```

- [ ] **Step 5.6: Add DEVIATION + implementation changelog entry to LLD 007**

  Append to Section 11 Changelog table:

  ```
  | 2026-03-23 | Implemented. Docker SHA pins, SBOM, cosign added to ci.yml. deploy.yml fully wired: run-migrations → deploy-staging → smoke-test-staging → deploy-production (manual gate, needs: [smoke-test-staging, run-migrations]) → smoke-test-production. Rollback job added. railway.toml created for scale-api and scale-worker. system-architecture.md updated. DEVIATION: all image references use github.repository_owner (matching existing ci.yml Push to GHCR step at line 236) rather than github.repository as documented in Section 4.4 — github.repository_owner is the correct form for GHCR image paths. |
  ```

- [ ] **Step 5.7: Commit**

  ```bash
  git add docs/design/system-architecture.md docs/features/007-cd-implementation.md
  git commit -m "docs: update system-architecture and mark LLD 007 as Implemented

  Refs: docs/features/007-cd-implementation.md"
  ```

---

## Verification Checklist (run locally before pushing PR)

| Check | Command | Expected |
|---|---|---|
| Docker SHA pins in ci.yml | `grep "docker/setup-buildx\|docker/build-push" .github/workflows/ci.yml` | Full SHAs, not `@v3`/`@v5` |
| SBOM step present | `grep "Generate SBOM" .github/workflows/ci.yml` | Step found |
| cosign step present | `grep "cosign sign" .github/workflows/ci.yml` | Step found |
| `id-token: write` present | `grep "id-token" .github/workflows/ci.yml` | Permission present |
| YAML valid — ci.yml | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"` | No exception |
| YAML valid — deploy.yml | `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/deploy.yml'))"` | No exception |
| railway.toml — both services | `grep "scale-api\|scale-worker" railway.toml` | Both service names present |
| All 7 deploy jobs present | `grep "^  [a-z].*:" .github/workflows/deploy.yml` | check-ci-success, run-migrations, deploy-staging, smoke-test-staging, deploy-production, smoke-test-production, rollback |
| deploy-production needs run-migrations | `grep -A2 "deploy-production:" .github/workflows/deploy.yml \| grep needs` | `[smoke-test-staging, run-migrations]` |
| LLD 007 status | `grep "Status" docs/features/007-cd-implementation.md` | `Implemented` |
