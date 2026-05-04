import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import MonthEndSnapshot from '../MonthEndSnapshot';

describe('MonthEndSnapshot', () => {
  it('renders three columns with formatted values', () => {
    render(<MonthEndSnapshot snapshot={{ p10: 12_400, p50: 28_500, p90: 44_800 }} />);
    expect(screen.getByTestId('month-end-p10')).toHaveTextContent('12,400');
    expect(screen.getByTestId('month-end-p50')).toHaveTextContent('28,500');
    expect(screen.getByTestId('month-end-p90')).toHaveTextContent('44,800');
  });

  it('handles floats by rounding to whole rupees', () => {
    render(<MonthEndSnapshot snapshot={{ p10: 1234.7, p50: 4567.4, p90: 7890.9 }} />);
    expect(screen.getByTestId('month-end-p10')).toHaveTextContent('1,235');
    expect(screen.getByTestId('month-end-p50')).toHaveTextContent('4,567');
  });

  it('renders zero values without crashing', () => {
    render(<MonthEndSnapshot snapshot={{ p10: 0, p50: 0, p90: 0 }} />);
    expect(screen.getByTestId('month-end-p10')).toBeInTheDocument();
  });
});
