/**
 * useWarmForecast — bounded-wait pre-warm hook.
 *
 * Per LLD 011 §WarmTrigger (Codex Fix #4 + Fix #5):
 *
 * - The page mount fires this hook AND ``getForecast(30)`` in parallel.
 * - Warm races a 1500 ms timeout (RFC-004 cold-load p95 budget).
 * - The explicit outcome (``ok | warming | timeout | error | 429``) is
 *   tracked in module-level state so a remount cannot relabel a prior
 *   timeout/429/error as ``ready``.
 * - Outcome telemetry posts to ``POST /api/v1/metrics/client-event``
 *   (fire-and-forget; never throws to the caller).
 *
 * Refs:
 *   docs/features/011-ai-insights-page.md §WarmTrigger
 *   docs/rfcs/RFC-004-tft-inference-cache-architecture.md §Codex Fix #4
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { ForecastApiError, postClientEvent, warmForecast } from '../api/forecast';
import type { WarmOutcome } from '../api/forecast.types';

/** Race timeout — matches RFC-004 §Success Metrics cold-load p95 budget. */
export const WARM_TIMEOUT_MS = 1500;

/** Idempotency window — bounded by the server's 5 min/user warm rate limit. */
const IDEMPOTENCY_WINDOW_MS = 1_000;

export type WarmState = 'idle' | 'warming' | WarmOutcome;

// Module-level sentinels prevent duplicate fires across StrictMode double-mounts
// and quick remounts. Resets on a full-page reload (module re-eval) — that is
// the correct behaviour: a fresh load is a fresh budget window for the user.
let inflight: Promise<WarmOutcome> | null = null;
let lastFiredAt = 0;

/** Reset module-level state — exposed for tests only. */
export function _resetWarmInflightForTests(): void {
  inflight = null;
  lastFiredAt = 0;
}

async function runWarmRace(): Promise<WarmOutcome> {
  let outcome: WarmOutcome;
  try {
    outcome = await Promise.race<WarmOutcome>([
      warmForecast().then(() => 'ok' as const),
      new Promise<'timeout'>(resolve => setTimeout(() => resolve('timeout'), WARM_TIMEOUT_MS)),
    ]);
  } catch (err: unknown) {
    if (err instanceof ForecastApiError && err.status === 429) {
      outcome = '429';
    } else {
      outcome = 'error';
    }
  }
  // Telemetry — fire-and-forget; postClientEvent already swallows errors.
  void postClientEvent('forecast_warm_outcome', outcome);
  return outcome;
}

export interface UseWarmForecastReturn {
  outcome: WarmState;
  fire: () => void;
}

/**
 * Returns the current warm state and an idempotent ``fire`` trigger.
 *
 * The hook auto-fires once on first mount (per `/insights` page contract).
 * The ``fire`` callback is exposed for explicit user-driven retries; calling
 * it more than once inside the 1-second idempotency window is a no-op.
 */
export function useWarmForecast(): UseWarmForecastReturn {
  const [outcome, setOutcome] = useState<WarmState>('idle');
  const cancelledRef = useRef(false);

  const fire = useCallback(() => {
    if (cancelledRef.current) return;
    const now = Date.now();
    if (inflight === null || now - lastFiredAt > IDEMPOTENCY_WINDOW_MS) {
      lastFiredAt = now;
      inflight = runWarmRace();
    }
    setOutcome('warming');
    const promise = inflight;
    promise.then(result => {
      if (!cancelledRef.current) setOutcome(result);
    });
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    // fire() flips state to 'warming' synchronously, then awaits the warm race.
    // This is the intentional state machine ('idle → warming → outcome'); the
    // setState here is the trigger transition, not a derived re-render.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fire();
    return () => {
      cancelledRef.current = true;
    };
  }, [fire]);

  return { outcome, fire };
}
