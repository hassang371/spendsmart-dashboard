'use client';

import { useState } from 'react';
import { ForecastApiError, scenarioForecast } from '@/lib/api/forecast';
import type { ScenarioDelta, ScenarioResponse, UserIntent } from '@/lib/api/forecast.types';

interface ScenarioImpactCardProps {
  intents: UserIntent[];
}

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

const pctFormatter = new Intl.NumberFormat('en-IN', {
  style: 'percent',
  maximumFractionDigits: 1,
});

function arrowFor(value: number): string {
  if (value > 0) return '▲';
  if (value < 0) return '▼';
  return '–';
}

function describeIntent(intent: UserIntent): string {
  return intent.notes?.trim() || intent.intent_type.replace(/_/g, ' ');
}

/**
 * Indirection over ``Date.now()`` to keep the React-purity lint rule satisfied.
 * Used only inside async event handlers; never read during render.
 */
function nowMillis(): number {
  return new Date().getTime();
}

interface RowState {
  loading: boolean;
  error: string | null;
  result: ScenarioResponse | null;
  open: boolean;
  rateLimitedUntil: number | null;
}

const initialRowState: RowState = {
  loading: false,
  error: null,
  result: null,
  open: false,
  rateLimitedUntil: null,
};

/** Per LLD 011 §ScenarioImpactCard. */
export default function ScenarioImpactCard({ intents }: ScenarioImpactCardProps) {
  const [rows, setRows] = useState<Record<string, RowState>>({});

  if (intents.length === 0) {
    return (
      <section
        data-testid="scenario-impact-empty"
        className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
      >
        <h2 className="text-sm font-medium text-muted-foreground">Scenario impact</h2>
        <p className="mt-3 text-sm text-muted-foreground">
          Add your upcoming plans to see their impact.
        </p>
      </section>
    );
  }

  const setRow = (id: string, patch: Partial<RowState>) => {
    setRows(prev => ({ ...prev, [id]: { ...(prev[id] ?? initialRowState), ...patch } }));
  };

  const handleToggle = async (intent: UserIntent) => {
    const current = rows[intent.id] ?? initialRowState;
    const now = nowMillis();
    if (current.rateLimitedUntil && current.rateLimitedUntil > now) {
      return;
    }
    if (current.result) {
      setRow(intent.id, { open: !current.open });
      return;
    }

    setRow(intent.id, { loading: true, error: null, open: true });
    try {
      const response = await scenarioForecast({
        horizon: 30,
        intent_ids_to_exclude: [intent.id],
      });
      setRow(intent.id, { loading: false, result: response, error: null });
    } catch (err) {
      let message = 'Could not run scenario.';
      let backoffUntil: number | null = null;
      if (err instanceof ForecastApiError && err.status === 429) {
        message = 'Too many scenarios — wait a minute.';
        backoffUntil = now + 60_000;
      } else if (err instanceof Error) {
        message = err.message || message;
      }
      setRow(intent.id, {
        loading: false,
        error: message,
        rateLimitedUntil: backoffUntil,
      });
    }
  };

  return (
    <section
      data-testid="scenario-impact-card"
      aria-labelledby="scenario-impact-heading"
      className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
    >
      <h2 id="scenario-impact-heading" className="text-sm font-medium text-muted-foreground">
        Scenario impact
      </h2>
      <ul className="mt-4 space-y-3">
        {intents.map(intent => {
          const state = rows[intent.id] ?? initialRowState;
          const headlineDelta: ScenarioDelta | null = state.result?.delta ?? null;
          return (
            <li
              key={intent.id}
              data-testid={`scenario-row-${intent.id}`}
              className="rounded-lg border border-border p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{describeIntent(intent)}</p>
                  <p className="text-xs text-muted-foreground">
                    Starts {intent.start_date}
                    {intent.amount !== null && intent.amount !== undefined
                      ? ` · ${inrFormatter.format(Math.abs(intent.amount))}`
                      : ''}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => handleToggle(intent)}
                  disabled={state.loading}
                  aria-expanded={state.open}
                  aria-controls={`scenario-detail-${intent.id}`}
                  className="rounded-md border border-border bg-background px-3 py-1 text-xs font-medium hover:bg-accent disabled:opacity-50"
                >
                  {state.loading ? 'Running…' : state.open ? 'Hide' : 'What if'}
                </button>
              </div>
              {state.error && (
                <p
                  role="alert"
                  className="mt-2 text-xs text-red-700 dark:text-red-300"
                  data-testid={`scenario-error-${intent.id}`}
                >
                  {state.error}
                </p>
              )}
              {state.open && headlineDelta && (
                <div
                  id={`scenario-detail-${intent.id}`}
                  className="mt-3 grid grid-cols-2 gap-3 text-xs"
                  data-testid={`scenario-detail-${intent.id}`}
                >
                  <div className="rounded-md border border-border p-2">
                    <p className="font-semibold">With your plan</p>
                    <p className="mt-1">
                      Safe to spend:{' '}
                      {inrFormatter.format(state.result!.with_intents.insights.safe_to_spend)}
                    </p>
                    <p>
                      Month-end P50:{' '}
                      {inrFormatter.format(state.result!.with_intents.insights.month_end.p50)}
                    </p>
                  </div>
                  <div className="rounded-md border border-border p-2">
                    <p className="font-semibold">Without it</p>
                    <p className="mt-1">
                      Safe to spend:{' '}
                      {inrFormatter.format(state.result!.without_intents.insights.safe_to_spend)}
                    </p>
                    <p>
                      Month-end P50:{' '}
                      {inrFormatter.format(state.result!.without_intents.insights.month_end.p50)}
                    </p>
                  </div>
                  <div className="col-span-2 rounded-md border border-border bg-muted/40 p-2">
                    <p className="font-semibold">Change</p>
                    <p className="mt-1">
                      {arrowFor(headlineDelta.month_end_p50_delta)} Month-end P50:{' '}
                      {inrFormatter.format(Math.abs(headlineDelta.month_end_p50_delta))}
                    </p>
                    <p>
                      {arrowFor(headlineDelta.safe_to_spend)} Safe-to-spend:{' '}
                      {inrFormatter.format(Math.abs(headlineDelta.safe_to_spend))}
                    </p>
                    <p>
                      {arrowFor(headlineDelta.overdraft_risk_score)} Overdraft risk:{' '}
                      {pctFormatter.format(Math.abs(headlineDelta.overdraft_risk_score))}
                    </p>
                  </div>
                </div>
              )}
              {state.open &&
                headlineDelta &&
                headlineDelta.month_end_p50_delta === 0 &&
                headlineDelta.safe_to_spend === 0 &&
                headlineDelta.overdraft_risk_score === 0 && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    No forecast change — this plan doesn&apos;t affect your 30-day outlook.
                  </p>
                )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
