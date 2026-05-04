'use client';

import { useEffect } from 'react';

interface InsightsErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function InsightsError({ error, reset }: InsightsErrorProps) {
  useEffect(() => {
    console.error('[insights] route error', error);
  }, [error]);

  return (
    <div
      role="alert"
      data-testid="insights-error-boundary"
      className="mx-auto flex max-w-2xl flex-col gap-3 p-6"
    >
      <h1 className="text-xl font-semibold">Forecast temporarily unavailable</h1>
      <p className="text-sm text-muted-foreground">
        We couldn&apos;t load your forecast. {error.message ? `(${error.message})` : ''}
      </p>
      <button
        type="button"
        onClick={() => reset()}
        className="self-start rounded-md border border-border bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
