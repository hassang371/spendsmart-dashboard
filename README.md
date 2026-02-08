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
```

Notes:
- Never commit real secret values.
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

## Import API

### Bulk import (POST)

`POST /api/import`

Headers:

```http
authorization: Bearer <SUPABASE_USER_ACCESS_TOKEN>
content-type: application/json
```

Body:

```json
{
  "transactions": [
    {
      "transaction_date": "2026-02-01T10:20:00.000Z",
      "amount": -5.5,
      "currency": "INR",
      "description": "Coffee",
      "merchant_name": "Cafe",
      "category": "Food",
      "payment_method": "upi",
      "status": "completed",
      "raw_data": { "source": "manual" }
    }
  ]
}
```

The target user is derived from the bearer token, not passed in the body.

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
