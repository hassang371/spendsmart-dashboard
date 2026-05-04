import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ConfidenceBadge from '../ConfidenceBadge';

describe('ConfidenceBadge', () => {
  it('renders population copy for chronos2 regardless of confidence', () => {
    render(<ConfidenceBadge modelType="chronos2" confidence="high" />);
    expect(screen.getByText(/Population model/i)).toBeInTheDocument();
  });

  it('renders high-confidence personalised copy', () => {
    render(<ConfidenceBadge modelType="tft_hybrid" confidence="high" />);
    expect(screen.getByText(/Personalised · high confidence/i)).toBeInTheDocument();
  });

  it('renders medium-confidence copy', () => {
    render(<ConfidenceBadge modelType="ensemble" confidence="medium" />);
    expect(screen.getByText(/medium confidence/i)).toBeInTheDocument();
  });

  it('renders low-confidence copy', () => {
    render(<ConfidenceBadge modelType="tft_hybrid" confidence="low" />);
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });
});
