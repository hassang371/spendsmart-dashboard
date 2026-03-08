---
paths:
  - "apps/web/**/*.ts"
  - "apps/web/**/*.tsx"
---

# Next.js / Frontend Rules (SCALE)

## App Router Conventions

- Pages live in `apps/web/app/` using App Router (not `pages/`)
- Layouts in `layout.tsx`, loading states in `loading.tsx`, errors in `error.tsx`
- Server Components by default — add `"use client"` only when browser APIs or React hooks are required

## Supabase SSR Pattern

```typescript
// Server Component — import from server module
import { createClient } from "@/lib/supabase/server"
const supabase = await createClient()

// Client Component — import from client module
import { createClient } from "@/lib/supabase/client"
const supabase = createClient()
```

Never import the server client into a client component — it will break.

## API Calls

- Use the API client in `apps/web/lib/api/client.ts` — do not call `fetch` directly
- Cache utilities live in `apps/web/lib/utils/cache.ts`

## Component Organization

```
apps/web/app/
  dashboard/
    page.tsx           ← thin route page, delegates to components
    layout.tsx
    transactions/page.tsx
    settings/page.tsx
  components/          ← shared components
  lib/                 ← utilities, API client, Supabase helpers
```

## TypeScript

- Strict mode enabled — no `any`, no `@ts-ignore` without an explanatory comment
- Run `npx tsc --noEmit` before claiming done

## Styling

- Tailwind CSS only — no inline styles, no CSS modules
- Check `apps/web/app/webflow-overrides.css` before adding global style overrides
