'use client';

import type { FloorSource } from '@/lib/api/forecast.types';

interface SafeToSpendCardProps {
  safeToSpend: number;
  floorUsed: number;
  floorSource: FloorSource;
}

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

/** Per LLD 011 §SafeToSpendCard. Clamps negative amounts to zero. */
export default function SafeToSpendCard({
  safeToSpend,
  floorUsed,
  floorSource,
}: SafeToSpendCardProps) {
  const clamped = Math.max(0, safeToSpend);
  const sourceLabel =
    floorSource === 'auto_p10_history'
      ? 'Floor calculated from your history'
      : 'Floor: your override';

  return (
    <section
      data-testid="safe-to-spend-card"
      aria-labelledby="safe-to-spend-heading"
      className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
    >
      <h2 id="safe-to-spend-heading" className="text-sm font-medium text-muted-foreground">
        Safe to spend
      </h2>
      <p className="mt-2 text-4xl font-bold tracking-tight" data-testid="safe-to-spend-amount">
        {inrFormatter.format(clamped)}
      </p>
      <p className="mt-3 text-sm text-muted-foreground">
        You can safely spend this before your P10 drops below{' '}
        <span className="font-medium text-foreground">{inrFormatter.format(floorUsed)}</span>.
      </p>
      <p className="mt-2 text-xs text-muted-foreground">
        {sourceLabel} ·{' '}
        <button
          type="button"
          disabled
          aria-disabled="true"
          className="cursor-not-allowed underline disabled:opacity-50"
          title="Floor override ships in v1.5"
        >
          edit
        </button>
      </p>
    </section>
  );
}
