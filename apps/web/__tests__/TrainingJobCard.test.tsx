import { render, screen, waitFor } from '@testing-library/react';
import TrainingJobCard from '../components/dashboard/TrainingJobCard';
import { apiGetLatestTrainingJob } from '../lib/api/client';
import { getBrowserSupabaseClient } from '../lib/supabase/client';
import { vi, describe, it, expect, beforeEach } from 'vitest';

vi.mock('../lib/api/client', () => ({
  apiGetLatestTrainingJob: vi.fn(),
}));

vi.mock('../lib/supabase/client', () => ({
  getBrowserSupabaseClient: vi.fn(),
}));

describe('TrainingJobCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    const mockSupabase = {
      auth: {
        getSession: vi.fn().mockResolvedValue({
          data: { session: { access_token: 'fake-token' } },
        }),
      },
    };
    (getBrowserSupabaseClient as any).mockReturnValue(mockSupabase);
  });

  it('shows idle state when no job exists', async () => {
    (apiGetLatestTrainingJob as any).mockResolvedValue(null);
    render(<TrainingJobCard />);
    await waitFor(() => {
      expect(screen.getByText(/model status/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/ready to train/i)).toBeInTheDocument();
  });

  it('shows training state', async () => {
    (apiGetLatestTrainingJob as any).mockResolvedValue({
      id: 'job-1',
      status: 'training',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    render(<TrainingJobCard />);
    await waitFor(() => {
      expect(screen.getByText(/training in progress/i)).toBeInTheDocument();
    });
  });

  it('shows completed state', async () => {
    (apiGetLatestTrainingJob as any).mockResolvedValue({
      id: 'job-2',
      status: 'completed',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    render(<TrainingJobCard />);
    await waitFor(() => {
      expect(screen.getByText(/model active/i)).toBeInTheDocument();
    });
  });

  it('shows failed state', async () => {
    (apiGetLatestTrainingJob as any).mockResolvedValue({
      id: 'job-3',
      status: 'failed',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    render(<TrainingJobCard />);
    await waitFor(() => {
      expect(screen.getByText(/training failed/i)).toBeInTheDocument();
    });
  });
});
