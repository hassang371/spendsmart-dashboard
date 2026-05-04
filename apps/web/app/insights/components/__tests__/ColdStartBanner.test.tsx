import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ColdStartBanner from '../ColdStartBanner';

describe('ColdStartBanner', () => {
  it('renders for chronos2 model', () => {
    render(<ColdStartBanner modelType="chronos2" confidence="high" />);
    expect(screen.getByTestId('cold-start-banner')).toBeInTheDocument();
    expect(screen.getByText(/personalised model is learning/i)).toBeInTheDocument();
  });

  it('renders for low confidence even on tft_hybrid', () => {
    render(<ColdStartBanner modelType="tft_hybrid" confidence="low" />);
    expect(screen.getByTestId('cold-start-banner')).toBeInTheDocument();
  });

  it('hides for high-confidence tft_hybrid', () => {
    const { container } = render(<ColdStartBanner modelType="tft_hybrid" confidence="high" />);
    expect(container.firstChild).toBeNull();
  });
});
