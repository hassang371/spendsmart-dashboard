import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import OverdraftRiskBadge from '../OverdraftRiskBadge';

const lowest = { date: '2026-04-22', p10: 1_200, p50: 4_500 };

describe('OverdraftRiskBadge', () => {
  it('hides when score < 0.1', () => {
    const { container } = render(<OverdraftRiskBadge score={0.05} lowest={lowest} floor={2_450} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders watch tier between 0.1 and 0.3', () => {
    render(<OverdraftRiskBadge score={0.2} lowest={lowest} floor={2_450} />);
    const badge = screen.getByTestId('overdraft-risk-badge');
    expect(badge).toHaveAttribute('data-tier', 'watch');
    expect(screen.getByText(/Watch/i)).toBeInTheDocument();
    expect(screen.getByText(/22 April/)).toBeInTheDocument();
  });

  it('renders risk tier at and above 0.3', () => {
    render(<OverdraftRiskBadge score={0.45} lowest={lowest} floor={2_450} />);
    const badge = screen.getByTestId('overdraft-risk-badge');
    expect(badge).toHaveAttribute('data-tier', 'risk');
    expect(screen.getByText('Risk')).toBeInTheDocument();
  });
});
