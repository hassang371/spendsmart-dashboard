'use client';

import { useCallback, useEffect, useState } from 'react';
import { ForecastApiError, getForecast, listIntents, upcomingIntents } from '@/lib/api/forecast';
import type { ForecastResponse, UserIntent } from '@/lib/api/forecast.types';
import AddPlanModal from '../../insights/components/AddPlanModal';
import BalanceForecastChart from '../../insights/components/BalanceForecastChart';
import ColdStartBanner from '../../insights/components/ColdStartBanner';
import ConfidenceBadge from '../../insights/components/ConfidenceBadge';
import MonthEndSnapshot from '../../insights/components/MonthEndSnapshot';
import OverdraftRiskBadge from '../../insights/components/OverdraftRiskBadge';
import PrimaryDrivers from '../../insights/components/PrimaryDrivers';
import SafeToSpendCard from '../../insights/components/SafeToSpendCard';
import ScenarioImpactCard from '../../insights/components/ScenarioImpactCard';
import WarmTrigger from '../../insights/components/WarmTrigger';

interface InsightsState {
  forecast: ForecastResponse | null;
  intents: UserIntent[];
  status: 'loading' | 'ready' | 'empty' | 'error';
  errorMessage: string | null;
}

const initialState: InsightsState = {
  forecast: null,
  intents: [],
  status: 'loading',
  errorMessage: null,
};

export default function InsightsPage() {
  const [state, setState] = useState<InsightsState>(initialState);

  const refetch = useCallback(async () => {
    setState(prev => ({ ...prev, status: 'loading', errorMessage: null }));
    try {
      const [forecast, intents] = await Promise.all([getForecast(30), listIntents()]);
      setState({ forecast, intents, status: 'ready', errorMessage: null });
    } catch (err) {
      if (err instanceof ForecastApiError && err.status === 400) {
        setState({
          forecast: null,
          intents: [],
          status: 'empty',
          errorMessage: err.message,
        });
        return;
      }
      const message = err instanceof Error ? err.message : 'Forecast request failed.';
      setState({ forecast: null, intents: [], status: 'error', errorMessage: message });
    }
  }, []);

  useEffect(() => {
    // refetch() is async — setState fires after the network promise settles,
    // not synchronously in the effect body. This is the canonical client-side
    // data-fetch pattern; the rule's heuristic flags it but it is correct.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refetch();
  }, [refetch]);

  // Poll every 60s + refetch when tab regains focus. Lets the page reflect
  // freshly-trained TFT models without a manual reload — once the worker
  // completes a training_jobs row + invalidates the cache, the next poll
  // tick picks up the personalised forecast.
  useEffect(() => {
    const onFocus = () => void refetch();
    window.addEventListener('focus', onFocus);
    const interval = window.setInterval(() => void refetch(), 60_000);
    return () => {
      window.removeEventListener('focus', onFocus);
      window.clearInterval(interval);
    };
  }, [refetch]);

  if (state.status === 'loading') {
    return (
      <div
        className="mx-auto flex w-full max-w-5xl flex-col gap-4"
        aria-busy="true"
        data-testid="insights-loading"
      >
        <WarmTrigger />
        <div className="h-8 w-1/3 animate-pulse rounded bg-muted" />
        <div className="h-64 w-full animate-pulse rounded-xl bg-muted" />
        <div className="grid gap-4 md:grid-cols-2">
          <div className="h-40 animate-pulse rounded-xl bg-muted" />
          <div className="h-40 animate-pulse rounded-xl bg-muted" />
        </div>
      </div>
    );
  }

  if (state.status === 'empty') {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4" data-testid="insights-empty">
        <h1 className="text-2xl font-semibold">No forecast yet</h1>
        <p className="text-sm text-muted-foreground">
          Connect a bank account to see your forecast. {state.errorMessage}
        </p>
        <a
          href="/dashboard/accounts"
          className="self-start rounded-md border border-border bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Connect an account
        </a>
      </div>
    );
  }

  if (state.status === 'error' || !state.forecast) {
    return (
      <div
        role="alert"
        data-testid="insights-error"
        className="mx-auto flex w-full max-w-2xl flex-col gap-3"
      >
        <h1 className="text-xl font-semibold">Forecast temporarily unavailable</h1>
        <p className="text-sm text-muted-foreground">
          {state.errorMessage ?? 'Something went wrong loading your forecast.'}
        </p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="self-start rounded-md border border-border bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          Try again
        </button>
      </div>
    );
  }

  const forecast = state.forecast;
  const insights = forecast.insights;
  const visibleIntents = upcomingIntents(state.intents, 10);

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-4" data-testid="insights-page">
      <WarmTrigger />
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">AI Insights</h1>
          <p className="text-sm text-muted-foreground">
            30-day forecast · model {forecast.model_version}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ConfidenceBadge modelType={forecast.model_type} confidence={forecast.confidence} />
          <AddPlanModal onCreated={() => void refetch()} />
        </div>
      </header>

      <ColdStartBanner modelType={forecast.model_type} confidence={forecast.confidence} />

      <BalanceForecastChart forecast={forecast.forecast} />

      <div className="grid gap-4 md:grid-cols-2">
        <SafeToSpendCard
          safeToSpend={insights.safe_to_spend}
          floorUsed={insights.floor_used}
          floorSource={insights.floor_source}
        />
        <MonthEndSnapshot snapshot={insights.month_end} />
      </div>

      <OverdraftRiskBadge
        score={insights.overdraft_risk_score}
        lowest={insights.lowest_balance}
        floor={insights.floor_used}
      />

      <PrimaryDrivers drivers={insights.primary_drivers} />

      <ScenarioImpactCard intents={visibleIntents} />
    </div>
  );
}
