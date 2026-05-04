import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ForecastApiError,
  FEATURE_LABEL_MAP,
  createIntent,
  getForecast,
  humanizeFeatureKey,
  postClientEvent,
  upcomingIntents,
  warmForecast,
} from '../forecast';
import { makeIntentFixture } from '../../../app/insights/components/insights_fixtures';

vi.mock('../../supabase/client', () => ({
  getBrowserSupabaseClient: () => ({
    auth: {
      getSession: () =>
        Promise.resolve({
          data: { session: { access_token: 'fake-token', user: { id: 'u' } } },
        }),
    },
  }),
}));

const originalFetch = globalThis.fetch;

function mockFetch(impl: (url: RequestInfo | URL, init?: RequestInit) => Promise<Response>) {
  globalThis.fetch = vi.fn(impl) as unknown as typeof fetch;
}

describe('lib/api/forecast', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn() as unknown as typeof fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('getForecast issues GET with horizon and bearer token', async () => {
    const captured: { url?: string; init?: RequestInit } = {};
    mockFetch(async (url, init) => {
      captured.url = String(url);
      captured.init = init;
      return new Response(JSON.stringify({ horizon: 30 }), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    });

    await getForecast(30);
    expect(captured.url).toMatch(/\/forecast\/predict\?horizon=30$/);
    const headers = captured.init?.headers as Record<string, string>;
    expect(headers?.authorization).toBe('Bearer fake-token');
  });

  it('clamps horizon to [1, 30]', async () => {
    const captured: { url?: string } = {};
    mockFetch(async url => {
      captured.url = String(url);
      return new Response('{}', {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    });
    await getForecast(999);
    expect(captured.url).toMatch(/horizon=30$/);
  });

  it('throws ForecastApiError with status on non-2xx', async () => {
    mockFetch(
      async () =>
        new Response(JSON.stringify({ detail: 'rate limit' }), {
          status: 429,
          headers: { 'content-type': 'application/json' },
        })
    );
    try {
      await warmForecast();
      throw new Error('expected throw');
    } catch (err) {
      expect(err).toBeInstanceOf(ForecastApiError);
      expect((err as ForecastApiError).status).toBe(429);
    }
  });

  it('createIntent serialises body as JSON', async () => {
    const captured: { init?: RequestInit } = {};
    mockFetch(async (_url, init) => {
      captured.init = init;
      return new Response(JSON.stringify(makeIntentFixture()), {
        status: 201,
        headers: { 'content-type': 'application/json' },
      });
    });
    await createIntent({
      intent_type: 'planned_large_expense',
      start_date: '2026-05-15',
      amount: 1000,
    });
    expect(captured.init?.method).toBe('POST');
    expect(captured.init?.body).toBe(
      JSON.stringify({
        intent_type: 'planned_large_expense',
        start_date: '2026-05-15',
        amount: 1000,
      })
    );
  });

  it('postClientEvent never throws even when fetch rejects', async () => {
    mockFetch(async () => {
      throw new Error('network down');
    });
    await expect(postClientEvent('forecast_warm_outcome', 'timeout')).resolves.toBeUndefined();
  });

  it('upcomingIntents sorts by start_date ascending', () => {
    const a = makeIntentFixture({ id: 'a', start_date: '2026-06-01' });
    const b = makeIntentFixture({ id: 'b', start_date: '2026-05-10' });
    const c = makeIntentFixture({ id: 'c', start_date: '2026-05-20', is_active: false });
    const sorted = upcomingIntents([a, b, c]);
    expect(sorted.map(i => i.id)).toEqual(['b', 'a']);
  });

  it('humanizeFeatureKey uses the label map and falls back', () => {
    expect(humanizeFeatureKey('is_payday')).toBe(FEATURE_LABEL_MAP.is_payday);
    expect(humanizeFeatureKey('totally_unknown_key')).toBe('Totally Unknown Key');
  });
});
