# Feature: AI Insights Page — Forecast UI v1

> **Doc ID:** 011-ai-insights-page
> **Date:** 2026-04-17
> **DRI:** Mohammed Hassan Mohiddin
> **Status:** Draft
> **Type:** Feature LLD

## Problem Statement

LLD 009 + RFC-003 + RFC-005 + LLD 010 deliver a fully-functional forecast backend: 7-quantile `ForecastPoint`, nested `ForecastInsights` with ten server-computed derived fields, `prediction_id` for audit, `POST /forecast/scenario` A/B endpoint, and `/forecast/intents/*` CRUD. None of this is visible to users today. The current Next.js 16 frontend has no `/insights` route; the existing `/dashboard` shows raw transactions, not forecasts.

Three concrete gaps:

1. **No UI surfaces the 7-quantile forecast or any of the ten insight fields.** The entire output of the TFT + Chronos-2 ensemble is computed server-side per request and thrown away because no client consumes it.
2. **No scenario UI.** Users cannot ask "what happens if I cancel the Goa trip?" despite the backend supporting it via `POST /forecast/scenario`. The "Scenario Impact Cards" component the Cowork synthesis identified has no home.
3. **No intent entry.** LLD 010 provides intent CRUD via HTTP but no human-usable form. A user with an upcoming vacation cannot tell SCALE about it, so the prediction engine's biggest improvement lever (Cowork synthesis §user intent capture) is structurally unreachable.

The Cowork synthesis identified ten candidate UI components derivable from the existing response shape. Shipping a subset of the most load-bearing seven makes the forecast product usable without waiting for exhaustive design polish.

## Success Criteria

- [ ] New route `apps/web/app/insights/page.tsx` renders for authenticated users; unauthenticated visitors redirected to `/login` via `apps/web/proxy.ts` matcher + `apps/web/lib/supabase/middleware.ts` auth gate (both extended in this feature)
- [ ] Seven components render with real data from `GET /api/v1/forecast/predict`: Balance Forecast Fan Chart, Safe-to-Spend Card, Month-End Snapshot, Overdraft Risk Indicator, Confidence Badge, Primary Drivers, Scenario Impact Cards
- [ ] Data fetch runs client-side via `lib/api/forecast.ts` wrappers (matching the existing `lib/api/client.ts` pattern used by `dashboard/page.tsx`). Loading skeleton replaced by populated view once the predict response resolves
- [ ] `POST /api/v1/forecast/warm` fires once on `/insights` route mount via `useWarmForecast()` hook. The hook tracks explicit outcome state (`ok | 429 | timeout | error`), races against a 1500 ms timeout, and posts the outcome to `POST /api/v1/metrics/client-event`. Does NOT fire from root layout (pre-auth routes). The forecast `useEffect` runs in parallel; predict is independent of warm outcome. No fire-and-forget; no swallowed 429.
- [ ] Scenario UI: clicking "what if" on a stored intent issues `POST /api/v1/forecast/scenario` with `intent_ids_to_exclude=[id]`, renders side-by-side before/after cards with delta numbers
- [ ] Intent entry: an "Add plan" button opens a framer-motion-based modal with a 7-type dropdown + conditional fields, POSTs to `/api/v1/forecast/intents`, re-fetches the insights payload in the same component tree
- [ ] Empty states: cold-start users (either `model_type="chronos2"` OR `confidence="low"`) see a "Building your personalised forecast" banner
- [ ] All components are TypeScript-typed against hand-written types in `apps/web/lib/api/forecast.ts` mirroring RFC-003 / LLD 010 Pydantic schemas; no `any` in component props
- [ ] CI test `apps/api/domains/forecasting/tests/test_frontend_schema_drift.py` fails if the Pydantic models' JSON-Schema diverges from `apps/web/lib/api/forecast.schema.json` (checked-in snapshot)
- [ ] Unit tests with Vitest + React Testing Library cover each component's three states: loading, populated, error
- [ ] Playwright + axe-core accessibility smoke asserts zero critical a11y violations on `/insights` with a synthetic authenticated fixture (Lighthouse-CI not in project scope; axe via Playwright matches existing `apps/web/e2e/` infrastructure)

## Scope

### In Scope

- `/insights` client-rendered route (matches existing `/dashboard` all-client pattern; RSC migration deferred to a separate future LLD — see §"Implementation corrections" below)
- Extend `apps/web/proxy.ts` matcher to include `/insights/:path*` and extend `apps/web/lib/supabase/middleware.ts` auth-gate to treat `/insights` as a protected route (today it only protects `/dashboard`)
- Seven UI components listed in Success Criteria
- Scenario UI (inline on `/insights`)
- Intent entry modal triggered by "Add plan" button (framer-motion-based — project does NOT use shadcn/ui; `framer-motion` is already in `apps/web/package.json`)
- Pre-warm fire from `/insights` route only (NOT from root layout, which also covers `/login`, `/signup`, marketing pages; firing `/forecast/warm` pre-auth would produce unauthenticated requests)
- Hand-written TypeScript types at `apps/web/lib/api/forecast.ts` mirroring RFC-003 / LLD 010 Pydantic schemas. No OpenAPI generator in repo today. Add a Python-side CI test `apps/api/domains/forecasting/tests/test_frontend_schema_drift.py` that loads both the Pydantic models and the generated JSON-Schema from `apps/web/lib/api/forecast.schema.json` (exported manually) and fails on drift — this is the cheaper equivalent of type-gen and enforces the contract in CI
- Rename / deprecate the existing `apps/web/lib/api/client.ts::ForecastResponse` interface (currently the statistical-MVP shape; will collide with the new 7-quantile `ForecastResponse`). Move legacy type to `LegacyForecastResponse` + add `@deprecated` JSDoc; point it at the upcoming removal in the cleanup commit
- Tailwind styling (reuse existing tokens from `app/globals.css`)
- Cold-start banner
- Error / empty / loading states per component

### Out of Scope

- Three Cowork-identified components deferred: Spending Forecast Breakdown (weekly bars), Upcoming Financial Events Timeline, Financial Weather Summary (narrative card). All derivable from the same response; ship-later when design polish lands
- Dedicated `/scenarios` page (inline modal sufficient for v1)
- Intent list management page (modal covers add; edit/delete flow via modal re-use)
- Onboarding tour for first-time users
- Mobile-specific breakpoints beyond Tailwind defaults (responsive via container queries; no native-app bridge)
- Chart export (PNG download, share URL)
- Historical forecast comparison ("how accurate were last month's predictions?" — needs `user_predictions` table read surface; deferred)
- Admin-only accuracy dashboard (`tft_cache_*` metrics from RFC-004)
- Drag-to-zoom on the fan chart
- Natural-language intent entry (LLM orchestrator path)
- Push notifications when intent start_date approaches

## Design

### Route Layout

```
apps/web/
  proxy.ts                        # MODIFY — add '/insights/:path*' to matcher
  lib/supabase/
    middleware.ts                 # MODIFY — add /insights to isDashboardRoute branch (rename the flag to isProtectedRoute for clarity)
  app/
    insights/
      page.tsx                    # NEW — CLIENT component; fetches predict + intents on mount via lib/api/forecast.ts
      loading.tsx                 # NEW — route-level skeleton (Next 16 App Router)
      error.tsx                   # NEW — must be 'use client' per Next 16 error boundary contract
      components/
        BalanceForecastChart.tsx  # client — recharts fan chart
        SafeToSpendCard.tsx       # client — pure display (page is client, so all children client-ready)
        MonthEndSnapshot.tsx      # client — pure display
        OverdraftRiskBadge.tsx    # client — conditional render
        ConfidenceBadge.tsx       # client — conditional copy
        PrimaryDrivers.tsx        # client — top-3 bar list
        ScenarioImpactCard.tsx    # client — scenario fetch on interaction
        AddPlanModal.tsx          # client — framer-motion-backed modal (NOT shadcn/ui)
        ColdStartBanner.tsx       # client — shown on (model_type="chronos2" OR confidence="low")
        WarmTrigger.tsx           # client — wraps useWarmForecast() bounded-wait hook (NO fire-and-forget)
        insights_fixtures.ts      # shared test fixtures
        __tests__/
          BalanceForecastChart.test.tsx
          SafeToSpendCard.test.tsx
          MonthEndSnapshot.test.tsx
          OverdraftRiskBadge.test.tsx
          ConfidenceBadge.test.tsx
          PrimaryDrivers.test.tsx
          ScenarioImpactCard.test.tsx
          AddPlanModal.test.tsx

apps/web/lib/api/
  client.ts                       # MODIFY — rename existing ForecastResponse → LegacyForecastResponse + @deprecated JSDoc
  forecast.ts                     # NEW — typed fetch wrappers for /api/v1/forecast/*;
                                  #       re-exports ForecastResponse, ForecastInsights, UserIntent,
                                  #       ScenarioResponse, IntentCreateRequest, IntentUpdateRequest types
                                  #       mirroring RFC-003 + LLD 010 schemas (hand-written)
  forecast.schema.json            # NEW — checked-in JSON-Schema snapshot of the Pydantic shapes;
                                  #       CI test asserts Pydantic → JSON-Schema round-trips to this file
  __tests__/
    forecast.test.ts              # NEW — fetch wrapper contract tests

apps/api/domains/forecasting/tests/
  test_frontend_schema_drift.py   # NEW — loads Pydantic models, generates JSON-Schema,
                                  # asserts equal to apps/web/lib/api/forecast.schema.json
```

### Data Flow

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant PX as 🛡️ proxy.ts middleware
    participant P as 📄 insights/page.tsx (client)
    participant WT as 🔥 WarmTrigger
    participant API as ⚙️ FastAPI (/api/v1)
    participant SVC as 📊 ForecastService

    Note over U,PX: Route gating
    U->>PX: GET /insights
    PX->>PX: Supabase session check (updated middleware.ts, /insights in matcher)
    alt unauthenticated
        PX-->>U: redirect to /login
    else authenticated
        PX-->>U: HTML shell for /insights

        Note over U,SVC: Initial data fetch (client-side, mirrors /dashboard pattern)
        U->>P: mount /insights
        P->>WT: WarmTrigger mounts once
        WT->>API: POST /api/v1/forecast/warm (raced against 1.5s timeout)
        API-->>WT: 202 (warm started) | 429 (rate-limited) | timeout
        WT->>API: POST /api/v1/metrics/client-event {result: "ok|429|timeout|error"}
        API->>SVC: background load via RFC-004 cache
        P->>API: GET /api/v1/forecast/predict?horizon=30 (client fetch w/ bearer)
        API->>SVC: predict(user_id, horizon=30)
        SVC-->>API: ForecastResponse (7 quantiles + insights + prediction_id)
        API-->>P: JSON payload
        P->>API: GET /api/v1/forecast/intents (parallel client fetch)
        API-->>P: UserIntent[]
        P-->>U: components render populated state (loading skeleton replaced)

        Note over U,API: Scenario interaction
        U->>P: click "what if" on stored intent
        P->>API: POST /api/v1/forecast/scenario { intent_ids_to_exclude: [id] }
        API-->>P: ScenarioResponse { with_intents, without_intents, delta }
        P-->>U: inline before/after render

        Note over U,API: Intent entry
        U->>P: click "Add plan" → fill modal → submit
        P->>API: POST /api/v1/forecast/intents { ... }
        API-->>P: UserIntent
        P->>API: GET /api/v1/forecast/predict (re-fetch via wrapper; replaces local state)
        P->>API: GET /api/v1/forecast/intents (re-fetch; replaces list state)
        P-->>U: updated forecast + intent list reflecting new intent
    end
```

> **Endpoint dependency note.** `GET /api/v1/forecast/predict` is introduced by the LLD 009 plan (Task 8, `docs/plans/2026-04-06-prediction-engine.md`) which adds a GET route to complement the existing `POST /api/v1/forecast/predict` CSV-upload endpoint. If LLD 011 implementation proceeds before LLD 009's Task 8, the client wrapper temporarily uses `POST /api/v1/forecast/predict` with an empty body until the GET route lands. Document this order-dependency in the implementation plan (Phase 3 master plan).

### Component Specifications

Each component consumes a typed slice of `ForecastResponse`. No component reaches for raw quantiles directly except the fan chart. Server components are the default; client boundaries are marked explicitly and kept minimal.

#### 1. BalanceForecastChart (client)

**Input:** `forecast: ForecastPoint[]` (30 items × 7 quantiles), `today: string`.

**Output:** recharts `AreaChart` with three stacked confidence bands:
- outer P2–P98 (15 % opacity)
- mid P10–P90 (30 % opacity)
- inner P25–P75 (50 % opacity)
- P50 line (solid)
- vertical marker at `today`

**Hover behaviour:** tooltip shows date + all 7 quantiles.

**Client-only** because recharts uses DOM measurement.

#### 2. SafeToSpendCard (server)

**Input:** `insights.safe_to_spend: number`, `insights.floor_used: number`, `insights.floor_source: "auto_p10_history" | "user_override"`.

**Output:**

```
₹14,200
You can safely spend this before your P10 drops below ₹2,450
Floor calculated from your history · [edit]
```

"[edit]" disabled in v1 (floor override is v1.5); visible as a placeholder so the affordance exists.

#### 3. MonthEndSnapshot (server)

**Input:** `insights.month_end: { p10, p50, p90 }`.

**Output:** three-column stat card:

```
Worst case    Likely      Best case
₹12,400       ₹28,500     ₹44,800
```

#### 4. OverdraftRiskBadge (server)

**Input:** `insights.overdraft_risk_score: number` (0..1), `insights.lowest_balance: { date, p10 }`.

**Output:**
- score < 0.1 → hidden (no badge when no risk)
- 0.1 ≤ score < 0.3 → yellow "Watch" badge + "3 days may dip below ₹2,450. Earliest risk: 22 April."
- score ≥ 0.3 → red "Risk" badge + same copy

#### 5. ConfidenceBadge (server)

**Input:** `confidence: "low" | "medium" | "high"`, `model_type: "chronos2" | "tft_hybrid" | "ensemble"`.

**Output:**
- `chronos2` → "Population model · getting to know your pattern"
- `tft_hybrid` / `ensemble` + `confidence="high"` → "Personalised · high confidence"
- other combinations → intermediate copy

Sets honest expectations and gives cold-start users a visible progression.

#### 6. PrimaryDrivers (server)

**Input:** `insights.primary_drivers: { feature, weight }[]` (top 3 by weight from RFC-003 / RFC-005 VSN).

**Output:** horizontal bar chart (pure CSS, no chart library) with human-readable labels:

```
Payday pattern        ████████████  42%
Day of week           ██████        22%
Recent balance level  ████          16%
```

Label mapping from feature keys (`is_payday`, `day_of_week`, `day_of_month`, etc.) to human strings lives in `lib/forecast-client.ts` as a const map.

#### 7. ScenarioImpactCard (client)

**Input:** list of active `UserIntent` fetched from `/forecast/intents`.

**Output:** one card per intent with a "what if" toggle. Clicking the toggle:

1. Issues `POST /forecast/scenario { horizon: 30, intent_ids_to_exclude: [intent.id] }`.
2. Renders a two-column compare view: "With your plan" vs "Without it".
3. Highlights `delta.month_end_p50_delta` + `delta.safe_to_spend` as the headline numbers.
4. Toggle state is component-local; no URL state in v1 (future: shareable scenario URLs).

**Client-only** because interaction is pure client state.

#### 8. AddPlanModal (client)

**Input:** none (purely write side).

**Output:** Framer-motion-animated modal (uses existing `framer-motion` dep — matches `dashboard/page.tsx` animation style) opened from an "Add plan" button. Implementation sketch: a `<motion.div>` backdrop + `<motion.div>` panel with `initial/animate/exit` variants; focus trap via `useFocusTrap` hook (trivial custom hook, ~20 lines) + ESC-to-close keydown listener. Does NOT depend on shadcn/ui, Radix, or HTML `<dialog>`. Form:

- `intent_type` dropdown (7 types)
- `start_date` date picker
- `end_date` date picker (hidden unless `is_recurring=true` or intent_type requires it)
- `amount` numeric input (hidden for LIFE_EVENT without-amount path; shown otherwise)
- `category_bucket` dropdown (RFC-005's 12 buckets, optional)
- `confidence` three-state toggle (low / medium / high; default medium)
- `is_recurring` checkbox
- `rrule_freq` dropdown (shown when `is_recurring=true`)
- `notes` textarea (max 280 chars, counter)

Conditional visibility driven by the Pydantic cross-field validators from LLD 010. Submit → `POST /forecast/intents` → on success close modal + `router.refresh()`. On 400 errors, render field-level messages parsed from FastAPI's validation response.

#### 9. ColdStartBanner (client)

**Input:** `model_type: string`, `confidence: string`.

**Output:** rendered when `model_type === "chronos2"` OR `confidence === "low"` (unifies cold-start detection across both signals; covers both brand-new users and users mid-retrain-cycle whose tier routed to Chronos despite prior history):

```
Your personalised model is learning.
Right now we're showing the population forecast.
A personalised version ships after you've had at least 90 days of transactions.
```

#### 10. WarmTrigger (client)

Mounts once on `/insights` only. Does **not** mount from root `app/layout.tsx` (that layout wraps `/login`, `/signup`, and marketing pages where the user has no session; firing `/forecast/warm` pre-auth returns 401 and is wasted traffic).

**Codex Fix #4 — observable warm with bounded wait + fallback.** The earlier
fire-and-forget design (`warmForecast().catch(() => {})`) hides every failure mode
and does NOT guarantee the cache is hot before the first `/forecast/predict` lands.
v1 contract:

- `WarmTrigger` returns a `warmPromise` that resolves on 202/200 or rejects on 4xx/timeout.
- The page component races `warmPromise` against a 1500ms timeout (the cold-load p95
  budget per RFC-004 §Success Metrics). Whichever resolves first lets the predict
  fetch proceed.
- Outcome telemetry: every warm attempt emits a Prometheus client-side counter via
  the existing structlog forwarding pattern — `forecast_warm_outcome_total{result="ok|429|timeout|error"}`.
  Server-side already counts `tft_cache_hits_total` vs `_misses_total`; the client
  counter closes the loop on warm success rate.

```typescript
'use client';
import { useEffect, useState } from 'react';
import { warmForecast } from '@/lib/api/forecast';

const WARM_TIMEOUT_MS = 1500;     // matches RFC-004 §Success Metrics cold-load p95 budget

type WarmOutcome = 'ok' | '429' | 'timeout' | 'error';
type WarmState   = 'idle' | 'warming' | WarmOutcome;

// Module-level outcome cache. Re-mounts within the 5-min RFC-004 rate-limit
// window read this rather than re-firing. Codex Fix #5 — track explicit
// outcome (not just promise resolution) so a remount cannot misreport a
// timeout/429/error as 'ok'/'ready'.
let inflight: Promise<WarmOutcome> | null = null;
let lastFiredAt = 0;

async function postOutcome(result: WarmOutcome): Promise<void> {
    try {
        await fetch('/api/v1/metrics/client-event', {
            method: 'POST', credentials: 'include',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ event: 'forecast_warm_outcome', result }),
        });
    } catch {
        /* telemetry must never throw to caller */
    }
}

async function runWarmRace(): Promise<WarmOutcome> {
    let outcome: WarmOutcome;
    try {
        outcome = await Promise.race<WarmOutcome>([
            warmForecast().then(() => 'ok' as const),
            new Promise<'timeout'>(r => setTimeout(() => r('timeout'), WARM_TIMEOUT_MS)),
        ]);
    } catch (err: unknown) {
        // warmForecast rejected (network/4xx/5xx); classify
        const status = (err as { status?: number } | undefined)?.status;
        outcome = status === 429 ? '429' : 'error';
    }
    void postOutcome(outcome);
    return outcome;
}

export function useWarmForecast(): WarmState {
    const [state, setState] = useState<WarmState>('idle');
    useEffect(() => {
        let cancelled = false;
        const since = Date.now() - lastFiredAt;
        const reuse = since < 5 * 60_000 && inflight !== null;
        const promise = reuse
            ? inflight!                           // existing race
            : (lastFiredAt = Date.now(), inflight = runWarmRace());
        setState('warming');
        promise.then(outcome => {
            if (!cancelled) setState(outcome);    // explicit outcome → state
        });
        return () => { cancelled = true; };
    }, []);
    return state;
}
```

The state machine is now explicit: `'idle' → 'warming' → ('ok' | '429' | 'timeout' | 'error')`. Remounts inside the 5-minute window adopt the same outcome. A timeout or 429 from a prior mount is **never silently relabeled `'ready'`**.

Page consumers branch on outcome value:

```typescript
const warm = useWarmForecast();
const showColdBanner = warm === 'timeout' || warm === 'error';
```

The page mount fires `useWarmForecast()` and `getForecast(30)` in parallel. If the
warm completes within 1.5 s, the cache is hot and the predict request hits a warm
path. If the warm times out or fails, the predict still proceeds — the user sees
either a cold-path response (slower but correct) or, if both fail, the existing
`error.tsx` fallback. Either way, telemetry records the outcome.

**Server-side counter:** `apps/api/core/metrics.py` adds an
eleventh counter `forecast_warm_outcome_total` with label `result` ∈
`{ok, 429, timeout, error}`, fed via a new `POST /api/v1/metrics/client-event` route
that accepts a small JSON body and increments the counter. The route is
JWT-authenticated and rate-limited at 30/min/user via the existing
`RateLimiter + rate_limit_dependency` pattern. (This route is added in the same
implementation stage as the WarmTrigger for symmetry.)

**Required test:** `WarmTrigger.test.tsx::test_predict_proceeds_when_warm_times_out`
mocks `warmForecast` to never resolve; asserts the page still renders the forecast
within an acceptable time once the predict response lands.

The `fired` flag resets on full-page reload (module re-eval), which is the correct behaviour — a fresh load is a fresh 5-minute window to the user.

### Data-fetching Contract

`apps/web/lib/api/forecast.ts` (new module; sibling to existing `client.ts`):

```typescript
// Thin typed wrappers over FastAPI forecast endpoints.
// Reuses the API_BASE_URL pattern + bearer-token pattern from lib/api/client.ts.
// Types hand-written to mirror RFC-003 + LLD 010 Pydantic schemas;
// apps/web/lib/api/forecast.schema.json is the checked-in contract snapshot;
// Python CI test test_frontend_schema_drift.py fails on drift.

import type {
    ForecastResponse, ForecastPoint, ForecastInsights,
    UserIntent, IntentCreateRequest, IntentUpdateRequest,
    ScenarioRequest, ScenarioResponse,
} from './forecast.types';          // co-located type declarations
import { getAuthHeader, API_BASE_URL } from './client';

export async function getForecast(horizon = 30): Promise<ForecastResponse> {
    const res = await fetch(`${API_BASE_URL}/forecast/predict?horizon=${horizon}`, {
        headers: await getAuthHeader(),
        credentials: 'include',
    });
    if (!res.ok) throw new ForecastError(res);
    return res.json();
}

export async function getIntents(): Promise<UserIntent[]> { ... }
export async function postIntent(body: IntentCreateRequest): Promise<UserIntent> { ... }
export async function postScenario(body: ScenarioRequest): Promise<ScenarioResponse> { ... }
export async function warmForecast(): Promise<void> { ... }   // throws on 4xx/5xx; useWarmForecast() races + branches
```

`API_BASE_URL` resolves to `process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'` (already set in `lib/api/client.ts:15`). All paths above are relative to `/api/v1`; the full URL is `${API_BASE_URL}/forecast/*`. This is cross-origin (browser → FastAPI); `credentials: 'include'` forwards the auth cookie. CORS on FastAPI must already allow the Next.js origin with credentials (verified via existing `client.ts` usage — the current statistical-MVP forecast client already does this successfully).

Type definitions live in `apps/web/lib/api/forecast.types.ts` as hand-written interfaces mirroring RFC-003 / LLD 010 Pydantic schemas. No OpenAPI generator exists in the repo; see Scope for the Python-side drift-check test that enforces contract fidelity.

### Client-Side Rendering Pattern

`insights/page.tsx` follows the existing `apps/web/app/dashboard/page.tsx` convention: **all-client**, `'use client'` at the top, fetches on mount via `useEffect` + local state. This is a deliberate choice to avoid introducing an RSC pattern the codebase does not currently use (`lib/supabase/server.ts` does not exist; adding it plus an RSC migration doubles this LLD's scope). The hybrid RSC path is flagged for a future LLD once the broader app is ready for RSC migration.

```typescript
'use client';
import { useEffect, useState } from 'react';
import { getForecast, getIntents } from '@/lib/api/forecast';
import { WarmTrigger } from './components/WarmTrigger';
// ... component imports

export default function InsightsPage() {
    const [forecast, setForecast] = useState<ForecastResponse | null>(null);
    const [intents, setIntents] = useState<UserIntent[]>([]);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        Promise.all([getForecast(30), getIntents()])
            .then(([f, i]) => { setForecast(f); setIntents(i); })
            .catch(e => setError(String(e)));
    }, []);

    if (error) return <ErrorCard message={error} />;
    if (!forecast) return <InsightsSkeleton />;

    return (
        <>
            <WarmTrigger />
            <ColdStartBanner model_type={forecast.model_type} confidence={forecast.confidence} />
            <BalanceForecastChart forecast={forecast.forecast} />
            <SafeToSpendCard {...forecast.insights} />
            <MonthEndSnapshot snapshot={forecast.insights.month_end} />
            <OverdraftRiskBadge
                score={forecast.insights.overdraft_risk_score}
                lowest={forecast.insights.lowest_balance} />
            <ConfidenceBadge model_type={forecast.model_type} confidence={forecast.confidence} />
            <PrimaryDrivers drivers={forecast.insights.primary_drivers} />
            <ScenarioImpactCard intents={upcomingIntents(intents, 10)} />
            <AddPlanModal onCreated={() => refetch()} />
        </>
    );
}
```

**Revalidation:** after `AddPlanModal` succeeds, the page re-fetches both `getForecast` and `getIntents` through a `refetch()` helper that re-runs the `useEffect` body. No `router.refresh()` needed since the page is all-client.

**Intent list capping:** `upcomingIntents(intents, 10)` returns the 10 nearest-future active intents. Scenario cards show up to 10 to keep the page scannable. A future "see all plans" link → dedicated management page (deferred).

## API Usage

No new endpoints. All paths prefixed with `/api/v1` per the existing client base URL. Consumed:

| Method | Endpoint | Component | Notes |
|---|---|---|---|
| GET | `/api/v1/forecast/predict?horizon=30` | `page.tsx` client | mount fetch; hero payload. Depends on LLD 009 plan Task 8 to land the GET route (current router is POST-only). |
| GET | `/api/v1/forecast/intents` | `page.tsx` client | parallel with predict |
| POST | `/api/v1/forecast/intents` | AddPlanModal | triggers `refetch()` inside the client component |
| POST | `/api/v1/forecast/scenario` | ScenarioImpactCard | one call per toggle click; 5/min/user rate limit |
| POST | `/api/v1/forecast/warm` | WarmTrigger | bounded-wait via `useWarmForecast()` (1.5s timeout race); outcome telemetry; 1/5min/user rate limit |
| POST | `/api/v1/metrics/client-event` | useWarmForecast | warm-outcome telemetry → `forecast_warm_outcome_total{result}`; 30/min/user rate limit |
| PATCH | `/api/v1/forecast/intents/{id}` | not used in v1 | edit flow deferred |
| DELETE | `/api/v1/forecast/intents/{id}` | not used in v1 | delete flow deferred |

## Database Changes

None. All reads and writes go through existing/LLD-010 endpoints.

## Edge Cases & Error Handling

| Scenario | Expected Behaviour |
|---|---|
| User not authenticated | Next.js middleware redirects to `/login` before RSC runs |
| `/forecast/predict` returns 5xx | `error.tsx` renders graceful "Forecast temporarily unavailable — try again" card; Sentry-logged |
| `/forecast/predict` returns 400 "No transaction data" (new user, 0 txns) | page renders a distinct empty state: "Connect a bank account to see your forecast" + link to `/accounts` |
| `POST /forecast/warm` returns 429 | `useWarmForecast` outcome state = `'429'`; outcome telemetry posted; predict proceeds in parallel via the page's separate `getForecast` call. Cold path tolerated as fallback. |
| Scenario endpoint returns 429 (rate-limited to 5/min/user) | show toast: "Too many scenarios — wait a minute"; disable toggle for 60 s |
| AddPlanModal submit returns 400 with per-field errors | render field-level error under each input |
| User has 0 active intents | ScenarioImpactCard renders empty state: "Add your upcoming plans to see their impact" |
| ScenarioResponse.delta values are all zero (SAVINGS_GOAL excluded etc.) | show "No forecast change — this plan doesn't affect your 30-day outlook" |
| Fan chart receives `forecast.length < 30` | Per RFC-003 Pydantic `min_length=1, max_length=30`, shorter horizons are legal. Recharts renders the available points; x-axis scale adjusts. Typical case (`horizon=30` default) always produces 30 points. |
| Quantile ordering violated (shouldn't happen per RFC-003 Pydantic validation, but defensive) | component logs to Sentry + renders P50-only line, skips bands |
| `model_type === "chronos2"` with `confidence === "high"` | impossible per RFC-003 §1 schema design; if observed, ConfidenceBadge defaults to low-confidence copy |
| `insights.primary_drivers === []` (Chronos-only path) | PrimaryDrivers renders "Drivers not available for the population model" message; hides the bars |
| Dark mode | all components use Tailwind semantic tokens (`bg-card`, `text-muted-foreground`); no hard-coded colors |
| Feature-flagged rollout | none in v1; launch behind `/insights` route without a gate. If we ever need a gate, GrowthBook integration is a separate RFC |

## Security Considerations

- **Authentication:** `apps/web/proxy.ts` middleware (extended by this feature to include `/insights` in its matcher) verifies Supabase session before the `/insights` route renders. If no session, redirects to `/login` before any HTML ships. Client-side `fetch` calls pull the bearer token via `lib/api/client.ts::getAuthHeader()` — the same path `/dashboard` already uses — and attach it as the `Authorization: Bearer <jwt>` header. `credentials: 'include'` additionally forwards Supabase's cookie for defence-in-depth.
- **Cross-origin traffic:** browser → FastAPI is cross-origin (`localhost:3000` → `localhost:8000`). CORS allow-list on FastAPI must include the Next.js origin with `allow_credentials=True`. Already working for `/dashboard`'s existing forecast traffic; no change needed.
- **No API tokens client-side beyond the JWT.** The bearer token is sourced from Supabase's session store via `@supabase/ssr`; never written to `localStorage` or exposed in URL params.
- **XSS:** all dynamic content goes through React's default escaping. The `notes` field in `UserIntent` is rendered as text, never `dangerouslySetInnerHTML`. Links inside notes are not auto-linkified in v1 (future: run through DOMPurify before rendering).
- **CSRF:** FastAPI's existing auth middleware requires the bearer header on every state-changing request; cookies alone are insufficient. Supabase cookie is `SameSite=Lax` for session refresh only.
- **Rate limits:** WarmTrigger fires on `/insights` mount — guarded by RFC-004's 1/5min limit server-side. Module-level `fired` sentinel (§Design #10) prevents duplicate fires inside the same tab session. StrictMode double-fire and dev hot-reload remounts hit 429 and are discarded.
- **PII:** intents may contain user-identifying text in `notes` (LLD 010 §Security flags this). The UI renders notes as plain text. No third-party scripts see the insights payload (no Google Analytics on `/insights` beyond existing app-wide tracking, which excludes the forecast payload body).
- **Privilege escalation:** frontend cannot override `user_id` — FastAPI derives it from the JWT. Even if a malicious client passes an intent_ids_to_exclude with UUIDs from another user, RLS prevents the service from seeing those rows → 404.

## Testing Strategy

### Unit tests (Vitest + React Testing Library)

- `BalanceForecastChart.test.tsx` — renders 30 points; tooltip shows all 7 quantiles on hover; no bands when forecast empty; P50 line always present
- `SafeToSpendCard.test.tsx` — renders amount correctly; shows floor label; clamps negative amounts to zero
- `MonthEndSnapshot.test.tsx` — renders three columns; accepts floats; formats INR
- `OverdraftRiskBadge.test.tsx` — hidden when score < 0.1; yellow at 0.2; red at 0.4; copy includes earliest-risk date
- `ConfidenceBadge.test.tsx` — correct copy for each (model_type, confidence) combination; handles the impossible high-confidence-chronos2 case defensively
- `PrimaryDrivers.test.tsx` — top 3 rendered; feature-key-to-label mapping applied; empty state for Chronos-only
- `ScenarioImpactCard.test.tsx` — toggle click calls postScenario with correct body; side-by-side render on response; rate-limit toast on 429
- `AddPlanModal.test.tsx` — conditional field visibility; Pydantic-error-to-field mapping; router.refresh() called on success

### Integration tests

- `insights/page.test.tsx` — mounts with a mocked `getForecast` returning a realistic fixture; asserts all 7 components render; asserts empty state when forecast returns 400 "no data"
- `WarmTrigger` lifecycle: fires once on mount, silently ignores 429

### Contract tests

- `lib/api/__tests__/forecast.test.ts` — fetch wrappers serialise bodies correctly; response types match interface shape
- `apps/api/domains/forecasting/tests/test_frontend_schema_drift.py` — Python-side: generates JSON-Schema from Pydantic models (RFC-003 `ForecastResponse`, LLD 010 `UserIntent` / `ScenarioRequest` / etc.) and asserts equality with the committed `apps/web/lib/api/forecast.schema.json`. Fails CI on drift in either direction.
- **Accessibility smoke (Playwright + axe-core):** a Playwright test under `apps/web/e2e/insights.spec.ts` navigates as a synthetic authenticated user, runs `@axe-core/playwright` against `/insights` in populated and empty states, and asserts zero WCAG 2.1 AA critical / serious violations. (Lighthouse-CI is not in the project's toolchain and is not in scope; axe-core via Playwright matches the existing e2e infrastructure.)

### Manual / visual QA

- Run `make dev`, navigate to `/insights` as a test user with a TFT-trained checkpoint, visually verify all 7 components
- Repeat as a cold-start user (no checkpoint) — confirm ColdStartBanner renders
- Open AddPlanModal, create each of the 7 intent types, verify backend state via Supabase Studio

## Related Documents

- Feature LLD: `docs/features/009-prediction-engine.md` — the backend this UI surfaces
- Feature LLD: `docs/features/010-user-intents-and-scenario-forecasting.md` — intent CRUD + scenario endpoint
- RFC: `docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md` — `ForecastResponse` + `ForecastInsights` contract
- RFC: `docs/rfcs/RFC-004-tft-inference-cache-architecture.md` — `POST /forecast/warm` wiring + rate limit
- RFC: `docs/rfcs/RFC-005-aggregation-strategy-three-tier-data-separation.md` — `primary_drivers` produced from per-bucket VSN; 12 category buckets for AddPlanModal dropdown
- Existing code: `apps/web/app/dashboard/page.tsx` — styling + component patterns to reuse
- Existing code: `apps/web/middleware.ts` — auth redirect pattern to mirror on `/insights`
- Future LLD: `docs/features/NNN-forecast-accuracy-dashboard.md` (not yet authored) — admin surface for RFC-006 walk-forward results and RFC-003 pinball metrics
- Design doc to update: none — frontend architecture is not yet HLD-formalised

## Changelog

| Date | Entry |
|---|---|
| 2026-04-17 | Initial draft. Seven of ten Cowork-identified components shipped in v1: fan chart, safe-to-spend card, month-end snapshot, overdraft risk badge, confidence badge, primary drivers, scenario impact cards. Deferred: weekly spend breakdown, events timeline, financial weather. Hybrid RSC + client-boundary data flow proposed. Pre-warm fires from root layout + /insights. Shadcn/ui Dialog proposed. OpenAPI type-gen script assumed. Status: Draft. |
| 2026-04-17 | Spec review pass 1 — corrected multiple factual errors about the codebase. (C1) Route protection: middleware lives at `apps/web/proxy.ts` (not `middleware.ts`), matcher currently dashboard-only, `lib/supabase/server.ts` does not exist. This LLD now explicitly extends `proxy.ts` matcher + `lib/supabase/middleware.ts` auth gate to cover `/insights`; does NOT introduce RSC or a server-side Supabase client (pivoted to all-client pattern matching `/dashboard`). (C2) OpenAPI type-gen script does not exist. Replaced with hand-written types in `apps/web/lib/api/forecast.types.ts` + checked-in `forecast.schema.json` snapshot + Python drift-check test. (C3) `shadcn/ui` is not a project dependency. Replaced with framer-motion-based modal (existing dep). (H1) API paths now correctly prefixed with `/api/v1` per `lib/api/client.ts` convention. (H2) `GET /forecast/predict` flagged as dependent on LLD 009 plan Task 8; fallback to POST with empty body if Task 8 has not shipped. (H3) WarmTrigger scoped to `/insights` route only — NOT root layout (root wraps pre-auth routes). (H4) Added module-level `fired` sentinel to WarmTrigger. (H5) Scenario cards capped at top 10 upcoming intents via `upcomingIntents()` helper. (H6) Fan-chart spec unified: typical 30 points; shorter horizons legal per RFC-003 schema. (H7) ColdStartBanner gating unified: `model_type === "chronos2"` OR `confidence === "low"`. Testing changed from Lighthouse-CI (not in project) to Playwright + axe-core (matches existing e2e infrastructure). Existing `lib/api/client.ts::ForecastResponse` renamed `LegacyForecastResponse` with deprecation marker to avoid type collision. Status: Draft. |
| 2026-04-17 | **Codex Fix #4** (medium) — paired with RFC-004 update. WarmTrigger was fire-and-forget (`warmForecast().catch(() => {})`) with no first-request latency guarantee and no telemetry. Replaced with `useWarmForecast()` hook returning state; bounded 1500ms wait races warm against predict so cold path remains correct; outcome telemetry posts to new `POST /api/v1/metrics/client-event` route feeding `forecast_warm_outcome_total{result=...}` counter. New required test `WarmTrigger.test.tsx::test_predict_proceeds_when_warm_times_out`. |
| 2026-04-17 | Codex pass-2 fixes. **Codex Fix #5** — useWarmForecast remount could relabel timeout/429/error as `'ready'` because timeout was modeled as a resolved outcome. Rewrote: explicit `WarmOutcome = 'ok' \| '429' \| 'timeout' \| 'error'` type; module-level `inflight: Promise<WarmOutcome>`; remounts inside 5-min window adopt the same outcome verbatim — no resolution-vs-rejection conflation. Stripped every remaining "fire-and-forget"/"swallow 429" reference from Success Criteria, route layout, sequence diagram, API table, edge-case table; sequence diagram now shows the bounded-wait race + telemetry post explicitly. Added `POST /api/v1/metrics/client-event` to API table. |
