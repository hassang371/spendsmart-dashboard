import { render, screen, waitFor } from '@testing-library/react';
import SafeToSpendCard from '../components/dashboard/SafeToSpendCard';
import { apiSafeToSpend } from '../lib/api/client';
import { getBrowserSupabaseClient } from '../lib/supabase/client';
import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('../lib/api/client', () => ({
  apiSafeToSpend: vi.fn(),
}));

vi.mock('../lib/supabase/client', () => ({
  getBrowserSupabaseClient: vi.fn(),
}));

// Mock Recharts because it doesn't render well in jsdom without sizing
vi.mock('recharts', () => {
  const OriginalModule = vi.importActual('recharts');
  return {
    ...OriginalModule,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: 800, height: 800 }}>{children}</div>
    ),
    AreaChart: ({ children }: any) => <div>{children}</div>,
    Area: () => <div>Area</div>,
    XAxis: () => <div>XAxis</div>,
    YAxis: () => <div>YAxis</div>,
    Tooltip: () => <div>Tooltip</div>,
  };
});

describe('SafeToSpendCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default Supabase mock
    const mockSupabase = {
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: { access_token: 'fake-token' } },
        }),
      },
    };
    (getBrowserSupabaseClient as any).mockReturnValue(mockSupabase);
  });

  it('shows loading state initially', () => {
    (apiSafeToSpend as any).mockImplementation(() => new Promise(() => {}));
    render(<SafeToSpendCard />);
    expect(screen.getByText(/calculating/i)).toBeInTheDocument();
  });

  it('renders safe amount and confidence when data loads', async () => {
    (apiSafeToSpend as any).mockResolvedValue({
      safe_amount: 15000,
      currency: 'INR',
      horizon_days: 7,
      confidence: 0.85,
      days_analyzed: 90,
      model: 'statistical_mvp',
      note: 'Test note',
    });

    render(<SafeToSpendCard />);

    await waitFor(() => {
      expect(screen.getByText('₹15,000')).toBeInTheDocument();
    });
    expect(screen.getByText(/85% confidence/i)).toBeInTheDocument();
    expect(screen.getByText(/statistical mvp/i)).toBeInTheDocument();
  });

  it('renders forecast chart when breakdown is available', async () => {
    (apiSafeToSpend as any).mockResolvedValue({
      safe_amount: 12000,
      currency: 'INR',
      horizon_days: 7,
      confidence: 0.95,
      days_analyzed: 120,
      model: 'tft_v1',
      note: 'AI prediction',
      forecast_breakdown: [
        { date: '2025-01-01', p10: 100, p50: 200, p90: 300 },
        { date: '2025-01-02', p10: 110, p50: 210, p90: 310 },
      ],
    });

    render(<SafeToSpendCard />);

    await waitFor(() => {
      expect(screen.getByText('₹12,000')).toBeInTheDocument();
    });
    expect(screen.getByText(/tft v1/i)).toBeInTheDocument();
    // We mocked Recharts, so we just check if the component didn't crash
    // In a real browser test we'd check for chart elements
  });

  it('handles error gracefully', async () => {
    (apiSafeToSpend as any).mockRejectedValue(new Error('API Error'));
    render(<SafeToSpendCard />);

    await waitFor(() => {
      expect(screen.getByText(/unable to load/i)).toBeInTheDocument();
    });
  });
});
