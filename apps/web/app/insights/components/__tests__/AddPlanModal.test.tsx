import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AddPlanModal from '../AddPlanModal';
import { makeIntentFixture } from '../insights_fixtures';
import { ForecastApiError } from '@/lib/api/forecast';
import * as forecastModule from '@/lib/api/forecast';

describe('AddPlanModal', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('opens and closes via trigger and ESC', async () => {
    render(<AddPlanModal />);
    fireEvent.click(screen.getByTestId('add-plan-trigger'));
    expect(await screen.findByTestId('add-plan-modal')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    await waitFor(() => {
      expect(screen.queryByTestId('add-plan-modal')).not.toBeInTheDocument();
    });
  });

  it('hides amount field for life_event', async () => {
    render(<AddPlanModal />);
    fireEvent.click(screen.getByTestId('add-plan-trigger'));
    await screen.findByTestId('add-plan-modal');
    fireEvent.change(screen.getByTestId('add-plan-intent-type'), {
      target: { value: 'life_event' },
    });
    expect(screen.queryByTestId('add-plan-amount')).not.toBeInTheDocument();
  });

  it('shows end-date and rrule when recurring is checked', async () => {
    render(<AddPlanModal />);
    fireEvent.click(screen.getByTestId('add-plan-trigger'));
    await screen.findByTestId('add-plan-modal');
    fireEvent.click(screen.getByTestId('add-plan-recurring'));
    expect(screen.getByTestId('add-plan-rrule-freq')).toBeInTheDocument();
    expect(screen.getByTestId('add-plan-end-date')).toBeInTheDocument();
  });

  it('submits and calls onCreated', async () => {
    const intent = makeIntentFixture();
    const spy = vi.spyOn(forecastModule, 'createIntent').mockResolvedValue(intent);
    const onCreated = vi.fn();
    render(<AddPlanModal onCreated={onCreated} />);
    fireEvent.click(screen.getByTestId('add-plan-trigger'));
    await screen.findByTestId('add-plan-modal');
    fireEvent.change(screen.getByTestId('add-plan-amount'), { target: { value: '5000' } });
    fireEvent.click(screen.getByTestId('add-plan-submit'));

    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
      expect(onCreated).toHaveBeenCalledWith(intent);
    });
  });

  it('renders field-level errors from FastAPI 422', async () => {
    vi.spyOn(forecastModule, 'createIntent').mockRejectedValue(
      new ForecastApiError('validation', 422, {
        detail: [{ loc: ['body', 'amount'], msg: 'amount is required' }],
      })
    );
    render(<AddPlanModal />);
    fireEvent.click(screen.getByTestId('add-plan-trigger'));
    await screen.findByTestId('add-plan-modal');
    fireEvent.click(screen.getByTestId('add-plan-submit'));
    expect(await screen.findByText(/amount is required/i)).toBeInTheDocument();
  });
});
