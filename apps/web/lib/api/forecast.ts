/**
 * Typed fetch wrappers over the FastAPI forecast endpoints.
 *
 * Mirrors the bearer-token + base-URL pattern in ``lib/api/client.ts`` but
 * keeps the new RFC-003 / LLD 010 / RFC-004 surfaces isolated so the legacy
 * statistical-MVP types in ``client.ts`` can be deprecated without breaking
 * the new ``/insights`` page.
 *
 * Refs:
 *   docs/features/011-ai-insights-page.md §Data-fetching Contract
 *   docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md
 *   docs/features/010-user-intents-and-scenario-forecasting.md
 *   docs/rfcs/RFC-004-tft-inference-cache-architecture.md
 */

import type {
  ClientEventRequest,
  ForecastResponse,
  IntentCreateRequest,
  IntentUpdateRequest,
  ScenarioRequest,
  ScenarioResponse,
  UserIntent,
  WarmOutcome,
} from './forecast.types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/** Error thrown by every wrapper when the backend returns a non-2xx. */
export class ForecastApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ForecastApiError';
  }
}

/** Pull the bearer JWT from the current Supabase session.
 *
 * Uses a lazy dynamic import so that consuming this module (and pulling
 * its types) does not force ``lib/supabase/client.ts`` to evaluate at
 * import time. That module throws when ``NEXT_PUBLIC_SUPABASE_*`` env
 * vars are absent — fine in the browser bundle, surprising in unit tests.
 */
async function getAuthToken(): Promise<string | null> {
  try {
    const mod = await import('../supabase/client');
    const supabase = mod.getBrowserSupabaseClient();
    const { data } = await supabase.auth.getSession();
    return data?.session?.access_token ?? null;
  } catch {
    return null;
  }
}

interface FetchJsonOptions {
  method?: string;
  body?: unknown;
  /** Skip throw-on-non-2xx — used only by ``warmForecast`` which classifies. */
  noThrow?: boolean;
}

async function fetchJson<T>(path: string, options: FetchJsonOptions = {}): Promise<T> {
  const { method = 'GET', body, noThrow = false } = options;
  const token = await getAuthToken();
  const headers: Record<string, string> = {};
  if (body !== undefined) headers['content-type'] = 'application/json';
  if (token) headers['authorization'] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    credentials: 'include',
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok && !noThrow) {
    let detail: unknown = undefined;
    try {
      detail = await res.json();
    } catch {
      /* empty body */
    }
    const detailMessage =
      typeof detail === 'object' && detail !== null && 'detail' in detail
        ? String((detail as { detail: unknown }).detail)
        : `${method} ${path} failed`;
    throw new ForecastApiError(detailMessage, res.status, detail);
  }

  if (res.status === 204 || res.status === 205) {
    return undefined as unknown as T;
  }
  const contentType = res.headers.get('content-type') ?? '';
  if (!contentType.includes('application/json')) {
    return undefined as unknown as T;
  }
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Forecast surface
// ---------------------------------------------------------------------------

export function getForecast(horizon: number = 30): Promise<ForecastResponse> {
  const safeHorizon = Math.min(Math.max(Math.trunc(horizon), 1), 30);
  return fetchJson<ForecastResponse>(`/forecast/predict?horizon=${safeHorizon}`);
}

export interface WarmResponse {
  status: 'ready' | 'warming' | 'failed';
  user_id: string;
}

/**
 * Pre-warm the TFT inference cache for the current user.
 *
 * Throws ``ForecastApiError`` on 4xx/5xx — useWarmForecast() catches and
 * classifies via the ``status`` field. The 5-min server-side rate limit
 * surfaces as a 429.
 */
export function warmForecast(): Promise<WarmResponse> {
  return fetchJson<WarmResponse>('/forecast/warm', { method: 'POST' });
}

/**
 * Fire-and-forget client-event telemetry.
 *
 * Per LLD 011 §WarmTrigger contract — must NEVER throw to the caller, even on
 * network failure. Best-effort. Returns void on every code path.
 */
export async function postClientEvent(
  event: ClientEventRequest['event'],
  result: WarmOutcome
): Promise<void> {
  try {
    await fetchJson<void>('/metrics/client-event', {
      method: 'POST',
      body: { event, result } satisfies ClientEventRequest,
    });
  } catch {
    /* telemetry errors are intentionally swallowed */
  }
}

// ---------------------------------------------------------------------------
// Intent CRUD — LLD 010
// ---------------------------------------------------------------------------

export function listIntents(): Promise<UserIntent[]> {
  return fetchJson<UserIntent[]>('/forecast/intents');
}

export function getIntent(id: string): Promise<UserIntent> {
  return fetchJson<UserIntent>(`/forecast/intents/${encodeURIComponent(id)}`);
}

export function createIntent(body: IntentCreateRequest): Promise<UserIntent> {
  return fetchJson<UserIntent>('/forecast/intents', { method: 'POST', body });
}

export function updateIntent(id: string, body: IntentUpdateRequest): Promise<UserIntent> {
  return fetchJson<UserIntent>(`/forecast/intents/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body,
  });
}

export function deleteIntent(id: string): Promise<void> {
  return fetchJson<void>(`/forecast/intents/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

export function scenarioForecast(req: ScenarioRequest): Promise<ScenarioResponse> {
  return fetchJson<ScenarioResponse>('/forecast/scenario', { method: 'POST', body: req });
}

// ---------------------------------------------------------------------------
// VSN feature → human label map
// ---------------------------------------------------------------------------

/**
 * Human-readable labels for the VSN feature keys produced by
 * ``aggregate_daily_panel`` (see ``packages/forecasting/dataset.py``).
 *
 * Unknown keys fall through ``humanizeFeatureKey`` → title-cased + underscores
 * dropped fallback so the UI never renders raw column names.
 */
export const FEATURE_LABEL_MAP: Readonly<Record<string, string>> = Object.freeze({
  is_payday: 'Payday pattern',
  day_of_week: 'Day of week',
  day_of_month: 'Day of month',
  month: 'Time of year',
  daily_income: 'Recent income',
  daily_spend: 'Recent spend',
  bucket_total: 'Recent activity',
  closing_balance: 'Recent balance level',
  scheduled_event_amount: 'Scheduled events',
  category_bucket: 'Spending category',
  time_idx: 'Time progression',
  group_id: 'Account profile',
});

export function humanizeFeatureKey(key: string): string {
  if (FEATURE_LABEL_MAP[key]) return FEATURE_LABEL_MAP[key];
  return key
    .split('_')
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

// ---------------------------------------------------------------------------
// Intent helpers
// ---------------------------------------------------------------------------

/**
 * Sort intents by next-occurrence ascending and slice to the top ``cap``.
 *
 * Falls back to ``start_date`` when ``next_occurrence_date`` is missing
 * (the field is optional today). Inactive intents are filtered out.
 */
export function upcomingIntents(intents: UserIntent[], cap: number = 10): UserIntent[] {
  return intents
    .filter(i => i.is_active !== false)
    .map(i => ({
      intent: i,
      sortKey: i.next_occurrence_date ?? i.start_date,
    }))
    .sort((a, b) => (a.sortKey < b.sortKey ? -1 : a.sortKey > b.sortKey ? 1 : 0))
    .slice(0, cap)
    .map(entry => entry.intent);
}

export { API_BASE_URL };
