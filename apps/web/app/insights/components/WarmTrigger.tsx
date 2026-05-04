'use client';

import { useWarmForecast, type WarmState } from '@/lib/hooks/useWarmForecast';

interface WarmTriggerProps {
  /** Optional callback fired whenever the outcome state changes (test/visibility hook). */
  onOutcomeChange?: (state: WarmState) => void;
}

/**
 * Mounts ``useWarmForecast`` once on `/insights` route mount.
 *
 * Renders nothing visible — the hook drives the cache pre-warm + telemetry.
 * The page-level forecast fetch proceeds in parallel regardless of warm
 * outcome (Codex Fix #4).
 */
export default function WarmTrigger({ onOutcomeChange }: WarmTriggerProps) {
  const { outcome } = useWarmForecast();
  if (onOutcomeChange) {
    onOutcomeChange(outcome);
  }
  return (
    <span
      aria-hidden="true"
      data-testid="warm-trigger"
      data-warm-state={outcome}
      className="sr-only"
    />
  );
}
