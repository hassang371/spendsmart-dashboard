# SCALE App: Secrets Management Policy

## Approved Secrets Stores

1. **GitHub Actions Secrets**: Dedicated to CI/CD runtime needs (e.g., `SUPABASE_SERVICE_ROLE_KEY` for integration tests, deploy tags).
2. **Supabase Vault / Database**: For third-party integration keys (e.g., LLM APIs, external banking APIs).
3. **Local `.env` files**: Strictly for local development. Always ignored via `.gitignore`.

## Scanning & CI Enforcement (SEC-1)

- **Gitleaks** runs on every PR and push to the `main` branch via the `.github/workflows/secret-scan.yml` GitHub Action.
- Merges are **blocked** automatically if any hardcoded secrets are detected.
- If a false positive occurs, developers must add a `.gitleaksignore` file with the specific hash, accompanied by a PR comment explaining the false positive.

## Key Rotation Schedule

- **Database Passwords**: Rotated every 90 days.
- **Supabase API Keys (Anon / Service Role)**: Rotated immediately upon any suspected breach. Service Role key is rotated at least annually.
- **JWT Secrets**: Rotated annually.

## Emergency Revocation Steps

1. **Rotate Credentials**: Immediately rotate compromised keys in the Supabase Dashboard (Settings -> API).
2. **Update CI/CD**: Update GitHub Actions Secrets with the new keys.
3. **Scrub History**: If a secret was leaked in Git commit history, use `git filter-repo` to completely excise the leaked secret from the repository tree.
4. **Notify Users**: If database infrastructure was compromised, initiate an incident report and notify affected users.
