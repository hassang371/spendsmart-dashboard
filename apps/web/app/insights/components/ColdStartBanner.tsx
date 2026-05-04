'use client';

import { useEffect, useState } from 'react';
import { getBrowserSupabaseClient } from '@/lib/supabase/client';
import type { ForecastConfidence, ModelType } from '@/lib/api/forecast.types';

interface ColdStartBannerProps {
  modelType: ModelType;
  confidence: ForecastConfidence;
}

type TrainingState = 'idle' | 'pending' | 'processing';

/**
 * Cold-start banner per LLD 011 §ColdStartBanner. Shown when either
 * ``model_type === 'chronos2'`` or ``confidence === 'low'``.
 *
 * When a training_job for the current user is in flight we surface
 * that state (Realtime-driven) so Hassan sees "Training in progress
 * — ETA ~3–5 min" instead of the generic population-fallback copy.
 */
export default function ColdStartBanner({ modelType, confidence }: ColdStartBannerProps) {
  const [trainingState, setTrainingState] = useState<TrainingState>('idle');

  useEffect(() => {
    let cancelled = false;
    let channel: ReturnType<typeof getBrowserSupabaseClient>['channel'] extends (
      ...args: infer _A
    ) => infer _R
      ? _R
      : never;

    const supabase = getBrowserSupabaseClient();

    void (async () => {
      const { data: userResp } = await supabase.auth.getUser();
      const userId = userResp.user?.id;
      if (cancelled || !userId) return;

      // Initial snapshot.
      const { data } = await supabase
        .from('training_jobs')
        .select('status')
        .eq('user_id', userId)
        .in('status', ['pending', 'queued', 'running', 'processing'])
        .limit(1)
        .maybeSingle();
      if (cancelled) return;
      if (data?.status === 'pending' || data?.status === 'queued') setTrainingState('pending');
      else if (data?.status === 'processing' || data?.status === 'running')
        setTrainingState('processing');
      else setTrainingState('idle');

      // Push updates: any change to a training_jobs row for this user.
      channel = supabase
        .channel(`cold_start_banner:training_jobs:${userId}`)
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'training_jobs',
            filter: `user_id=eq.${userId}`,
          },
          (payload: { new: Record<string, unknown> | null }) => {
            const next =
              payload.new && typeof payload.new === 'object'
                ? (payload.new as { status?: string }).status
                : undefined;
            if (next === 'pending' || next === 'queued') setTrainingState('pending');
            else if (next === 'processing' || next === 'running') setTrainingState('processing');
            else setTrainingState('idle');
          }
        )
        .subscribe();
    })();

    return () => {
      cancelled = true;
      if (channel) {
        const supabase = getBrowserSupabaseClient();
        void supabase.removeChannel(channel);
      }
    };
  }, []);

  const shouldShow = modelType === 'chronos2' || confidence === 'low' || trainingState !== 'idle';
  if (!shouldShow) return null;

  // Active training takes priority over generic cold-start copy.
  if (trainingState === 'processing') {
    return (
      <div
        role="status"
        aria-live="polite"
        data-testid="cold-start-banner"
        className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-100"
      >
        <p className="font-semibold">Training your personalised model now…</p>
        <p className="mt-1">
          ETA 3–5 minutes on a M-series Mac. The page refreshes automatically when it&apos;s done —
          no need to reload.
        </p>
      </div>
    );
  }

  if (trainingState === 'pending') {
    return (
      <div
        role="status"
        aria-live="polite"
        data-testid="cold-start-banner"
        className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-100"
      >
        <p className="font-semibold">Personalised model queued for training.</p>
        <p className="mt-1">
          Showing the population forecast meanwhile. We&apos;ll refresh this page automatically when
          training finishes.
        </p>
      </div>
    );
  }

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
