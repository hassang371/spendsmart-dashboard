/**
 * Hand-written TypeScript types mirroring the FastAPI Pydantic models in
 * ``apps/api/domains/forecasting/schemas.py``.
 *
 * The drift-check Python test
 * ``apps/api/domains/forecasting/tests/test_frontend_schema_drift.py`` regenerates
 * the JSON-Schema bundle from those Pydantic models and asserts equality with
 * ``apps/web/lib/api/forecast.schema.json``. If a backend schema changes without
 * regenerating the snapshot, CI fails.
 *
 * Refs:
 *   docs/features/011-ai-insights-page.md §Data-fetching Contract
 *   docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §1
 *   docs/features/010-user-intents-and-scenario-forecasting.md §Domain Model
 */

// ---------------------------------------------------------------------------
// RFC-003 — ForecastResponse + nested shapes
// ---------------------------------------------------------------------------

/** One predicted day's full 7-quantile distribution. */
export interface ForecastPoint {
  /** YYYY-MM-DD */
  date: string;
  p2: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p98: number;
}

/** One ``(feature, weight)`` pair from the TFT Variable Selection Network. */
export interface VariableImportance {
  feature: string;
  weight: number;
}

/** A point-in-time snapshot of the P10/P50/P90 distribution. */
export interface QuantileSnapshot {
  p10: number;
  p50: number;
  p90: number;
}

/** The horizon day where P10 is minimised, plus its P10/P50. */
export interface LowestBalance {
  /** YYYY-MM-DD */
  date: string;
  p10: number;
  p50: number;
}

export type FloorSource = 'auto_p10_history' | 'user_override';

/** Server-computed derived insights for one forecast call. */
export interface ForecastInsights {
  lowest_balance: LowestBalance;
  /** Day 30 of horizon (rolling, not calendar). */
  month_end: QuantileSnapshot;
  predicted_monthly_spend: number;
  predicted_monthly_income: number;
  confidence_band_width: number;
  /** Top 3 from VSN; empty for chronos2. */
  primary_drivers: VariableImportance[];
  safe_to_spend: number;
  /** Fraction of horizon days with P10 below floor, [0, 1]. */
  overdraft_risk_score: number;
  floor_used: number;
  floor_source: FloorSource;
}

export type ModelType = 'chronos2' | 'tft_hybrid' | 'ensemble';
export type ForecastConfidence = 'low' | 'medium' | 'high';

/** Full forecast payload returned by both predict endpoints. */
export interface ForecastResponse {
  forecast: ForecastPoint[];
  model_type: ModelType;
  model_version: string;
  horizon: number;
  confidence: ForecastConfidence;
  variable_importance: VariableImportance[] | null;
  insights: ForecastInsights;
  /** UUID — generated server-side before the fire-and-forget INSERT. */
  prediction_id: string;
}

// ---------------------------------------------------------------------------
// LLD 010 — User intents + scenario forecasting
// ---------------------------------------------------------------------------

/** Seven intent types per LLD 010 — values are lowercased snake_case. */
export type IntentType =
  | 'income_change'
  | 'planned_large_expense'
  | 'life_event'
  | 'obligation_change'
  | 'savings_goal'
  | 'fd_maturity'
  | 'expected_bonus';

/** Tiered confidence per LLD 010. */
export type IntentConfidence = 'low' | 'medium' | 'high';

/** RRule frequency — only the five values the backend accepts. */
export type RRuleFreq = 'monthly' | 'weekly' | 'biweekly' | 'quarterly' | 'annual';

/** Allowed category buckets — kept in lockstep with backend allowlist. */
export type CategoryBucket =
  | 'salary'
  | 'rent'
  | 'groceries'
  | 'dining'
  | 'transport'
  | 'utilities'
  | 'entertainment'
  | 'health'
  | 'emi_loan'
  | 'investment'
  | 'transfer'
  | 'other';

/** Full read-shape of a row in ``public.user_intents``. */
export interface UserIntent {
  id: string;
  user_id: string;
  intent_type: IntentType;
  amount: number | null;
  amount_delta: number | null;
  category_bucket: CategoryBucket | string | null;
  /** YYYY-MM-DD */
  start_date: string;
  /** YYYY-MM-DD */
  end_date: string | null;
  confidence: IntentConfidence;
  is_recurring: boolean;
  rrule_freq: RRuleFreq | null;
  notes: string | null;
  is_active: boolean;
  /** ISO datetime string from the backend. */
  created_at: string;
  /** ISO datetime string from the backend. */
  updated_at: string;
  /**
   * Forward-looking helper field — not in the Pydantic shape today but
   * computed client-side by ``upcomingIntents()`` for sort stability.
   * Not serialised back to the API.
   */
  next_occurrence_date?: string;
}

export interface IntentCreateRequest {
  intent_type: IntentType;
  amount?: number | null;
  amount_delta?: number | null;
  category_bucket?: CategoryBucket | string | null;
  start_date: string;
  end_date?: string | null;
  confidence?: IntentConfidence;
  is_recurring?: boolean;
  rrule_freq?: RRuleFreq | null;
  notes?: string | null;
}

export interface IntentUpdateRequest {
  amount?: number | null;
  amount_delta?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  confidence?: IntentConfidence | null;
  notes?: string | null;
  is_active?: boolean | null;
}

export interface ScenarioRequest {
  horizon?: number;
  intent_ids_to_exclude?: string[];
  ephemeral_intents?: IntentCreateRequest[];
}

export interface ScenarioDelta {
  safe_to_spend: number;
  overdraft_risk_score: number;
  predicted_monthly_spend: number;
  predicted_monthly_income: number;
  month_end_p50_delta: number;
  confidence_band_width_delta: number;
}

export interface ScenarioResponse {
  with_intents: ForecastResponse;
  without_intents: ForecastResponse;
  delta: ScenarioDelta;
  applied_intents: UserIntent[];
  excluded_intents: UserIntent[];
}

// ---------------------------------------------------------------------------
// Client-event telemetry — see RFC-004 §Codex Fix #4
// ---------------------------------------------------------------------------

export type WarmOutcome = 'ok' | '429' | 'timeout' | 'error';
export type ClientEventName = 'forecast_warm_outcome';

export interface ClientEventRequest {
  event: ClientEventName;
  result: WarmOutcome;
}
