# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SCALE is a financial transaction management dashboard built with Next.js 16 (App Router) and Supabase. The app allows users to track transactions, view analytics, and manage multiple accounts. It's deployed on Vercel and uses Google OAuth for authentication.

## Development Commands

```bash
# Install dependencies (from dashboard directory)
cd dashboard
npm install

# Run development server
npm run dev  # Starts at http://localhost:3000

# Build for production
npm run build

# Lint
npm run lint

# Python tools (requires .venv activation)
cd tools
python import_transactions.py <file_path> --user_id <uuid>
```

## Architecture

### Directory Structure

- `dashboard/` - Next.js application (primary codebase)
  - `app/` - App Router pages and API routes
  - `lib/` - Shared utilities (Supabase client, privacy utilities)
  - `components/` - React components
  - `public/` - Static assets
- `tools/` - Python scripts for data import
- `architecture/` - Database schema and documentation

### Authentication Flow

- Uses `@supabase/ssr` for server-side auth management
- Middleware (`middleware.ts`) handles session validation and route protection:
  - Unauthenticated users accessing `/dashboard/*` are redirected to `/login`
  - Authenticated users on `/login` or `/signup` are redirected to `/dashboard`
  - Authenticated users on `/` are redirected to `/dashboard`
- Multi-account support: Users can switch between multiple Google accounts via profile menu
  - Sessions stored in `localStorage` under `supabase-multi-auth`
  - Account switching uses `supabase.auth.setSession()`
- OAuth callback handled at `/auth/callback/route.ts`

### Supabase Client Initialization

- **Client Components**: Use `lib/supabase/client.ts` → exports `supabase` singleton
  - Uses `createBrowserClient()` from `@supabase/ssr`
- **Middleware**: Uses `lib/supabase/middleware.ts` → `createServerClient()` with cookie handling
- **API Routes**: Create client directly with `createClient()` from `@supabase/supabase-js` and pass user's bearer token in headers

### Database Schema

Single table: `transactions`
- Fields: `id`, `user_id`, `transaction_date`, `amount`, `currency`, `description`, `merchant_name`, `category`, `payment_method`, `status`, `created_at`, `raw_data`
- Row Level Security (RLS) enabled - users can only access their own transactions
- Indexes on `(user_id, transaction_date)` and `category`
- See `architecture/schema.sql` for full schema

### Import API

`POST /api/import` - Bulk transaction import endpoint
- Requires `Authorization: Bearer <user_access_token>` header
- User ID derived from token (NOT in request body)
- Accepts up to 5000 transactions per request
- Performs deduplication via fingerprint: `{date}|{amount}|{description}`
- Validated with Zod schemas (`ImportTransactionSchema`)

### Python Import Script

`tools/import_transactions.py` - CLI tool for batch CSV/Excel ingestion
- Supports both CSV and Excel (`.xls`, `.xlsx`)
- Normalizes headers to lowercase with underscores
- Required columns: `date`, `amount`, `description`
- Handles debit/credit types (converts debits to negative amounts)
- Batch inserts (100 records at a time)
- Usage: `python import_transactions.py <file> --user_id <uuid>`

### Privacy Utilities

`lib/privacy.ts` - Transaction anonymization for AI processing
- `anonymizeTransaction()` - Strips user IDs, optionally masks merchant names
- `anonymizeDataset()` - Batch anonymization
- Scrubs PII (emails, phone numbers) from descriptions via regex

### Theme System

- Uses `next-themes` for light/dark mode
- Theme toggle in sidebar (clicking SCALE logo with Sun/Moon icon)
- Provider setup in `app/layout.tsx`
- Tailwind configured with CSS variables for theme colors

### Routing Structure

- `/` - Landing page (redirects to `/dashboard` if authenticated)
- `/login` - Google OAuth login
- `/signup` - Registration (also via Google OAuth)
- `/auth/callback` - OAuth callback handler
- `/dashboard` - Overview page
- `/dashboard/transactions` - Transaction list
- `/dashboard/analytics` - Charts and insights (MonthlyComparison, CategoryDistribution, SpendingHeatmap, MerchantLeaderboard)
- `/dashboard/settings` - User settings

## Environment Variables

Required in `dashboard/.env.local`:
```bash
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

For Python tools (`.env` in project root):
```bash
SUPABASE_URL=  # or NEXT_PUBLIC_SUPABASE_URL
SUPABASE_SERVICE_KEY=  # or SUPABASE_KEY or NEXT_PUBLIC_SUPABASE_ANON_KEY
```

## Deployment Workflow

1. Develop locally with `npm run dev`
2. Create feature branch (`fix/...` or `feat/...`)
3. Push to GitHub
4. Validate on Vercel preview URL
5. Merge to `main` only when verified

This prevents unnecessary production redeploys while maintaining fast feedback.

## Key Technical Details

### Multi-Account System (dashboard/app/dashboard/layout.tsx)

- Stores array of sessions in `localStorage` as `StoredSession[]`
- Each session includes: `user_id`, `email`, `name`, `avatar_url`, `access_token`, `refresh_token`, `expires_at`
- On auth state change, current session is upserted into storage
- Profile menu shows all stored sessions with checkmark on active account
- Invalid sessions are automatically removed when switch fails
- "Add Account" triggers sign-out then redirects to `/login`

### Middleware Session Management

- `updateSession()` in `lib/supabase/middleware.ts` runs on every matched route
- Creates server client with cookie handlers (`getAll`, `setAll`)
- Calls `supabase.auth.getUser()` to validate session
- Returns `NextResponse.redirect()` for unauthorized access or `NextResponse.next()` to continue

### Data Deduplication

- API route (`/api/import/route.ts`) uses fingerprint-based deduplication
- Fingerprint format: `{ISO_date_slice(0,19)}|{amount.toFixed(2)}|{lowercase_trimmed_description}`
- Duplicates within request payload are filtered before insert
- No DB-level duplicate checking (relies on fingerprint uniqueness)

## Common Patterns

### Fetching Transactions (Client Components)

```typescript
import { supabase } from "@/lib/supabase/client";

const { data, error } = await supabase
  .from("transactions")
  .select("*")
  .order("transaction_date", { ascending: false });
```

### Using Privacy Utilities

```typescript
import { anonymizeDataset } from "@/lib/privacy";

const anonymized = anonymizeDataset(transactions, {
  maskMerchant: true,
  scrubDescription: true
});
```

### Theme Toggle

```typescript
import { useTheme } from "next-themes";

const { theme, setTheme } = useTheme();
setTheme(theme === "dark" ? "light" : "dark");
```
