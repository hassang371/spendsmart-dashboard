/**
 * Shared test fixtures for the insights page suite.
 *
 * Mirror the RFC-003 ForecastResponse + LLD 010 UserIntent shapes exactly
 * as emitted by the backend; do NOT add fields here that the Pydantic
 * models do not produce — the schema-drift CI test won't catch FE-only
 * fictions.
 */

import type {
  ForecastInsights,
  ForecastPoint,
  ForecastResponse,
  UserIntent,
} from '@/lib/api/forecast.types';

export function makeForecastPoint(
  date: string,
  base: number,
  spread: number = 1500
): ForecastPoint {
  return {
    date,
    p2: base - spread * 1.6,
    p10: base - spread,
    p25: base - spread * 0.4,
    p50: base,
    p75: base + spread * 0.4,
    p90: base + spread,
    p98: base + spread * 1.6,
  };
}

export function makeForecastFixture(overrides: Partial<ForecastResponse> = {}): ForecastResponse {
  const points: ForecastPoint[] = Array.from({ length: 30 }, (_, i) => {
    const day = String(i + 1).padStart(2, '0');
    return makeForecastPoint(`2026-04-${day}`, 25_000 + i * 250);
  });

  const insights: ForecastInsights = {
    lowest_balance: { date: '2026-04-12', p10: 12_300, p50: 18_400 },
    month_end: { p10: 14_000, p50: 28_500, p90: 44_800 },
    predicted_monthly_spend: 38_000,
    predicted_monthly_income: 60_000,
    confidence_band_width: 12_500,
    primary_drivers: [
      { feature: 'is_payday', weight: 0.42 },
      { feature: 'day_of_week', weight: 0.22 },
      { feature: 'closing_balance', weight: 0.16 },
    ],
    safe_to_spend: 14_200,
    overdraft_risk_score: 0.05,
    floor_used: 2_450,
    floor_source: 'auto_p10_history',
  };

  return {
    forecast: points,
    model_type: 'tft_hybrid',
    model_version: 'v1.0.0',
    horizon: 30,
    confidence: 'high',
    variable_importance: insights.primary_drivers,
    insights,
    prediction_id: '00000000-0000-4000-8000-000000000000',
    ...overrides,
  };
}

export function makeIntentFixture(overrides: Partial<UserIntent> = {}): UserIntent {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    user_id: '22222222-2222-4222-8222-222222222222',
    intent_type: 'planned_large_expense',
    amount: 45_000,
    amount_delta: null,
    category_bucket: 'entertainment',
    start_date: '2026-05-15',
    end_date: null,
    confidence: 'high',
    is_recurring: false,
    rrule_freq: null,
    notes: 'Goa trip',
    is_active: true,
    created_at: '2026-04-17T10:00:00.000Z',
    updated_at: '2026-04-17T10:00:00.000Z',
    ...overrides,
  };
}
