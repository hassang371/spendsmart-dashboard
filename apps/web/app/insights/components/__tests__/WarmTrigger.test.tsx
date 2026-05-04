import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import WarmTrigger from '../WarmTrigger';
import * as forecastModule from '@/lib/api/forecast';
import * as hookModule from '@/lib/hooks/useWarmForecast';

describe('WarmTrigger / useWarmForecast', () => {
  beforeEach(() => {
    hookModule._resetWarmInflightForTests();
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it('renders an invisible mount-time element with state', async () => {
    vi.spyOn(forecastModule, 'warmForecast').mockResolvedValue({
      status: 'ready',
      user_id: 'u1',
    });
    vi.spyOn(forecastModule, 'postClientEvent').mockResolvedValue();

    render(<WarmTrigger />);
    await waitFor(() => {
      expect(screen.getByTestId('warm-trigger')).toHaveAttribute('data-warm-state', 'ok');
    });
  });

  it('test_predict_proceeds_when_warm_times_out: outcome=timeout when warm never resolves', async () => {
    vi.spyOn(forecastModule, 'warmForecast').mockImplementation(
      () => new Promise(() => {}) // never resolves
    );
    const tele = vi.spyOn(forecastModule, 'postClientEvent').mockResolvedValue();

    render(<WarmTrigger />);

    // Real timers: race the actual 1500 ms WARM_TIMEOUT_MS. The component should
    // settle into outcome='timeout' and the predict path is unblocked.
    await waitFor(
      () => {
        expect(screen.getByTestId('warm-trigger')).toHaveAttribute('data-warm-state', 'timeout');
      },
      { timeout: 3_000 }
    );
    expect(tele).toHaveBeenCalledWith('forecast_warm_outcome', 'timeout');
  });

  it('classifies a 429 from warmForecast', async () => {
    vi.spyOn(forecastModule, 'warmForecast').mockRejectedValue(
      new forecastModule.ForecastApiError('rate', 429)
    );
    vi.spyOn(forecastModule, 'postClientEvent').mockResolvedValue();

    render(<WarmTrigger />);
    await waitFor(() => {
      expect(screen.getByTestId('warm-trigger')).toHaveAttribute('data-warm-state', '429');
    });
  });
});
