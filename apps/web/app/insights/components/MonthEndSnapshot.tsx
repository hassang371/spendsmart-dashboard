'use client';

import type { QuantileSnapshot } from '@/lib/api/forecast.types';

interface MonthEndSnapshotProps {
  snapshot: QuantileSnapshot;
}

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

/** Per LLD 011 §MonthEndSnapshot — three-column stat card. */
export default function MonthEndSnapshot({ snapshot }: MonthEndSnapshotProps) {
  return (
    <section
      data-testid="month-end-snapshot"
      aria-labelledby="month-end-heading"
      className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
    >
      <h2 id="month-end-heading" className="text-sm font-medium text-muted-foreground">
        Month-end snapshot
      </h2>
      <div className="mt-4 grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Worst case</p>
          <p className="mt-1 text-xl font-semibold" data-testid="month-end-p10">
            {inrFormatter.format(snapshot.p10)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Likely</p>
          <p className="mt-1 text-xl font-semibold" data-testid="month-end-p50">
            {inrFormatter.format(snapshot.p50)}
          </p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Best case</p>
          <p className="mt-1 text-xl font-semibold" data-testid="month-end-p90">
            {inrFormatter.format(snapshot.p90)}
          </p>
        </div>
      </div>
    </section>
  );
}
