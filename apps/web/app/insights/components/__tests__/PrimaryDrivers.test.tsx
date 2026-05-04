import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import PrimaryDrivers from '../PrimaryDrivers';

describe('PrimaryDrivers', () => {
  it('renders top 3 drivers with humanised labels', () => {
    render(
      <PrimaryDrivers
        drivers={[
          { feature: 'is_payday', weight: 0.42 },
          { feature: 'day_of_week', weight: 0.22 },
          { feature: 'closing_balance', weight: 0.16 },
          { feature: 'extra', weight: 0.05 },
        ]}
      />
    );
    expect(screen.getByText('Payday pattern')).toBeInTheDocument();
    expect(screen.getByText('Day of week')).toBeInTheDocument();
    expect(screen.getByText('Recent balance level')).toBeInTheDocument();
    expect(screen.queryByText(/Extra/)).not.toBeInTheDocument();
  });

  it('renders empty state when drivers is empty', () => {
    render(<PrimaryDrivers drivers={[]} />);
    expect(screen.getByText(/Drivers not available/i)).toBeInTheDocument();
  });

  it('falls back to humanised key for unknown features', () => {
    render(<PrimaryDrivers drivers={[{ feature: 'mystery_feature', weight: 1 }]} />);
    expect(screen.getByText('Mystery Feature')).toBeInTheDocument();
  });
});
