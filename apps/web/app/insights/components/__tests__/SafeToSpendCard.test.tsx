import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import SafeToSpendCard from '../SafeToSpendCard';

describe('SafeToSpendCard (insights)', () => {
  it('renders the formatted amount and floor', () => {
    render(
      <SafeToSpendCard safeToSpend={14_200} floorUsed={2_450} floorSource="auto_p10_history" />
    );
    expect(screen.getByTestId('safe-to-spend-amount')).toHaveTextContent('14,200');
    expect(screen.getByText(/Floor calculated from your history/i)).toBeInTheDocument();
  });

  it('clamps negative amounts to zero', () => {
    render(<SafeToSpendCard safeToSpend={-500} floorUsed={1_000} floorSource="auto_p10_history" />);
    expect(screen.getByTestId('safe-to-spend-amount')).toHaveTextContent(/0/);
  });

  it('shows override label when applicable', () => {
    render(<SafeToSpendCard safeToSpend={5_000} floorUsed={1_500} floorSource="user_override" />);
    expect(screen.getByText(/Floor: your override/i)).toBeInTheDocument();
  });
});
