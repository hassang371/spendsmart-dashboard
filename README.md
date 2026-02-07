# SpendSmart Dashboard

SpendSmart is a Next.js dashboard app backed by Supabase Auth and Postgres.

## Stack

- Next.js App Router
- Supabase (`@supabase/supabase-js`)
- Tailwind CSS

## Environment Variables

Create `dashboard/.env.local` with:

```bash
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=

# For manual CSV ingestion API
INGEST_API_KEY=

# For Vercel cron auth (Vercel sends Authorization: Bearer $CRON_SECRET)
CRON_SECRET=

# For scheduled ingestion source
INGEST_CSV_URL=
INGEST_DEFAULT_USER_ID=
```

Notes:
- Never commit real secret values.
- `SUPABASE_SERVICE_ROLE_KEY` is server-only.
- `NEXT_PUBLIC_*` values are safe for browser usage.

## Local Development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Google OAuth Setup (Supabase)

1. In Supabase: `Authentication -> Providers -> Google`, enable Google and set client ID/secret.
2. In Google Cloud OAuth client, add callback URL:
   - `https://<your-project-ref>.supabase.co/auth/v1/callback`
3. In Supabase Auth URL config:
   - Site URL: your production app URL
   - Additional redirect URLs: `http://localhost:3000/auth/callback`

Login uses `signInWithOAuth` and returns through `/auth/callback`.

## Ingestion API

### Manual ingestion (POST)

`POST /api/ingest`

Headers:

```http
x-ingest-key: <INGEST_API_KEY>
content-type: application/json
```

Body:

```json
{
  "userId": "<uuid>",
  "csv": "Date,Description,Amount,Category\n2026-02-01,Coffee,-5.5,Food"
}
```

### Scheduled ingestion (Vercel Cron GET)

`GET /api/ingest`

Requirements:
- `CRON_SECRET` configured in Vercel
- `INGEST_CSV_URL` configured
- `INGEST_DEFAULT_USER_ID` configured

`vercel.json` runs this route daily at midnight UTC.

## Version Control + Deployment Workflow

Recommended workflow to avoid constant production redeploys:

1. Develop locally with `npm run dev`.
2. Create a feature branch (`fix/...`).
3. Push branch to GitHub.
4. Validate on Vercel preview URL.
5. Merge into `main` only when verified.

This keeps production stable while still giving fast feedback.

## Useful Commands

```bash
npm run dev
npm run lint
npm run build
```
