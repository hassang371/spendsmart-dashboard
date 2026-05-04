import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ScenarioImpactCard from '../ScenarioImpactCard';
import { makeForecastFixture, makeIntentFixture } from '../insights_fixtures';
import { ForecastApiError } from '@/lib/api/forecast';
import * as forecastModule from '@/lib/api/forecast';

describe('ScenarioImpactCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders empty state when no intents', () => {
    render(<ScenarioImpactCard intents={[]} />);
    expect(screen.getByText(/Add your upcoming plans/i)).toBeInTheDocument();
  });

  it('calls scenarioForecast with the intent id when toggled', async () => {
    const fixtureForecast = makeForecastFixture();
    const intent = makeIntentFixture();
    const spy = vi.spyOn(forecastModule, 'scenarioForecast').mockResolvedValue({
      with_intents: fixtureForecast,
      without_intents: fixtureForecast,
      delta: {
        safe_to_spend: 1_500,
        overdraft_risk_score: 0.02,
        predicted_monthly_spend: -2_000,
        predicted_monthly_income: 0,
        month_end_p50_delta: -3_000,
        confidence_band_width_delta: 0,
      },
      applied_intents: [],
      excluded_intents: [intent],
    });

    render(<ScenarioImpactCard intents={[intent]} />);
    fireEvent.click(screen.getByRole('button', { name: /What if/i }));

    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({
        horizon: 30,
        intent_ids_to_exclude: [intent.id],
      });
    });
    await screen.findByTestId(`scenario-detail-${intent.id}`);
  });

  it('shows rate-limit message on 429', async () => {
    const intent = makeIntentFixture();
    vi.spyOn(forecastModule, 'scenarioForecast').mockRejectedValue(
      new ForecastApiError('rate limited', 429)
    );

    render(<ScenarioImpactCard intents={[intent]} />);
    fireEvent.click(screen.getByRole('button', { name: /What if/i }));

    expect(await screen.findByText(/Too many scenarios — wait a minute/i)).toBeInTheDocument();
  });
});
