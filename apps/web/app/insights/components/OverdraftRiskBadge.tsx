'use client';

import type { LowestBalance } from '@/lib/api/forecast.types';

interface OverdraftRiskBadgeProps {
  score: number;
  lowest: LowestBalance;
  floor: number;
}

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

const dateFormatter = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'long' });

/** Per LLD 011 §OverdraftRiskBadge — hidden < 0.1, yellow 0.1..0.3, red ≥ 0.3. */
export default function OverdraftRiskBadge({ score, lowest, floor }: OverdraftRiskBadgeProps) {
  if (score < 0.1) return null;

  const tier: 'watch' | 'risk' = score < 0.3 ? 'watch' : 'risk';
  const palette =
    tier === 'watch'
      ? 'border-yellow-300 bg-yellow-50 text-yellow-900 dark:border-yellow-700 dark:bg-yellow-950 dark:text-yellow-100'
      : 'border-red-300 bg-red-50 text-red-900 dark:border-red-700 dark:bg-red-950 dark:text-red-100';
  const label = tier === 'watch' ? 'Watch' : 'Risk';

  let earliestRisk = lowest.date;
  try {
    const parsed = new Date(`${lowest.date}T00:00:00`);
    if (!Number.isNaN(parsed.getTime())) {
      earliestRisk = dateFormatter.format(parsed);
    }
  } catch {
    /* fall back to raw date string */
  }

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="overdraft-risk-badge"
      data-tier={tier}
      className={`flex items-start gap-3 rounded-lg border p-4 text-sm ${palette}`}
    >
      <span className="rounded-full px-2 py-0.5 text-xs font-bold uppercase tracking-wide ring-1 ring-current">
        {label}
      </span>
      <p>
        Some days may dip below {inrFormatter.format(floor)}. Earliest risk:{' '}
        <span className="font-medium">{earliestRisk}</span>.
      </p>
    </div>
  );
}
