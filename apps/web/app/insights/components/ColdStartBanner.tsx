'use client';

import type { ForecastConfidence, ModelType } from '@/lib/api/forecast.types';

interface ColdStartBannerProps {
  modelType: ModelType;
  confidence: ForecastConfidence;
}

/**
 * Cold-start banner per LLD 011 §ColdStartBanner. Shown when either
 * ``model_type === 'chronos2'`` or ``confidence === 'low'``.
 */
export default function ColdStartBanner({ modelType, confidence }: ColdStartBannerProps) {
  const shouldShow = modelType === 'chronos2' || confidence === 'low';
  if (!shouldShow) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="cold-start-banner"
      className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
    >
      <p className="font-semibold">Your personalised model is learning.</p>
      <p className="mt-1">
        Right now we&apos;re showing the population forecast. A personalised version ships after
        you&apos;ve had at least 90 days of transactions.
      </p>
    </div>
  );
}
