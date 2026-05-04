'use client';

import { humanizeFeatureKey } from '@/lib/api/forecast';
import type { VariableImportance } from '@/lib/api/forecast.types';

interface PrimaryDriversProps {
  drivers: VariableImportance[];
}

/** Per LLD 011 §PrimaryDrivers — top-3 horizontal bars (CSS only). */
export default function PrimaryDrivers({ drivers }: PrimaryDriversProps) {
  const top = drivers.slice(0, 3);

  if (top.length === 0) {
    return (
      <section
        data-testid="primary-drivers"
        aria-labelledby="primary-drivers-heading"
        className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
      >
        <h2 id="primary-drivers-heading" className="text-sm font-medium text-muted-foreground">
          What drives your forecast
        </h2>
        <p className="mt-3 text-sm text-muted-foreground">
          Drivers not available for the population model.
        </p>
      </section>
    );
  }

  const total = top.reduce((acc, d) => acc + Math.abs(d.weight), 0) || 1;

  return (
    <section
      data-testid="primary-drivers"
      aria-labelledby="primary-drivers-heading"
      className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
    >
      <h2 id="primary-drivers-heading" className="text-sm font-medium text-muted-foreground">
        What drives your forecast
      </h2>
      <ul className="mt-4 space-y-3">
        {top.map(d => {
          const pct = Math.round((Math.abs(d.weight) / total) * 100);
          return (
            <li key={d.feature} className="flex items-center gap-3">
              <span className="w-44 shrink-0 text-sm font-medium" title={d.feature}>
                {humanizeFeatureKey(d.feature)}
              </span>
              <div
                className="relative h-3 flex-1 overflow-hidden rounded-full bg-muted"
                aria-hidden="true"
              >
                <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
              </div>
              <span className="w-12 shrink-0 text-right text-sm tabular-nums text-muted-foreground">
                {pct}%
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
