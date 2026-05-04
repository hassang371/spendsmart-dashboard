import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import BalanceForecastChart from '../BalanceForecastChart';
import { makeForecastFixture } from '../insights_fixtures';

vi.mock('recharts', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('recharts');
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <div style={{ width: 800, height: 400 }} data-testid="responsive-container">
        {children}
      </div>
    ),
  };
});

describe('BalanceForecastChart', () => {
  it('renders the chart canvas with 30 forecast points', () => {
    const fixture = makeForecastFixture();
    render(<BalanceForecastChart forecast={fixture.forecast} />);
    expect(screen.getByTestId('balance-forecast-chart-canvas')).toBeInTheDocument();
    expect(fixture.forecast).toHaveLength(30);
  });

  it('renders empty state when forecast is empty', () => {
    render(<BalanceForecastChart forecast={[]} />);
    expect(screen.getByText(/No forecast data available/i)).toBeInTheDocument();
  });

  it('renders at minimum-length horizon (1 point)', () => {
    const fixture = makeForecastFixture();
    render(<BalanceForecastChart forecast={fixture.forecast.slice(0, 1)} />);
    expect(screen.getByTestId('balance-forecast-chart-canvas')).toBeInTheDocument();
  });
});
