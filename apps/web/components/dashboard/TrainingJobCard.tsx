'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { BrainCircuit, Loader2, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { trainingApi, type TrainingJob } from '../../lib/api/client';
import { getCachedData, setCachedData } from '../../lib/utils/cache';
import { getBrowserSupabaseClient } from '../../lib/supabase/client';

const TRAINING_JOB_CACHE_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours (terminal states are immutable)

export default function TrainingJobCard() {
  const [job, setJob] = useState<TrainingJob | null>(null);
  const [loading, setLoading] = useState(true);
  // Ref tracks terminal state so fetchJob (stable, [] deps) can skip re-fetches
  const isTerminalRef = useRef(false);

  const fetchJob = useCallback(async () => {
    if (isTerminalRef.current) return;
    try {
      const supabase = getBrowserSupabaseClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        setJob(null);
        return;
      }

      const cacheKey = `training-job-cache:${session.user.id}`;

      // Only restore cache for terminal states — active jobs must always poll live
      const cachedData = getCachedData<TrainingJob | null>(cacheKey, TRAINING_JOB_CACHE_TTL_MS);

      if (cachedData !== undefined && cachedData !== null) {
        const isTerminal = cachedData.status === 'completed' || cachedData.status === 'failed';
        if (isTerminal) {
          setJob(cachedData);
          isTerminalRef.current = true;
          return;
        }
      }

      const latestJob = await trainingApi.getLatest(session.access_token);
      setJob(latestJob);
      if (latestJob?.status === 'completed' || latestJob?.status === 'failed') {
        isTerminalRef.current = true;
        // Cache terminal states — they're immutable so safe to keep for the session
        setCachedData(cacheKey, latestJob);
      }
    } catch {
      setJob(null);
    } finally {
      setLoading(false);
    }
  }, []); // stable — no deps, uses ref for terminal check

  useEffect(() => {
    fetchJob();
    const interval = setInterval(fetchJob, 30000);
    return () => clearInterval(interval);
  }, [fetchJob]); // fetchJob is stable so this runs once

  if (loading) {
    return (
      <div className="group relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-indigo-500 to-violet-600 p-6 text-white shadow-xl">
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-white/70" />
          <span className="text-sm font-medium text-white/70">Checking model status...</span>
        </div>
      </div>
    );
  }

  // Determine UI based on status
  let statusColor = 'from-indigo-500 to-violet-600';
  let icon = <BrainCircuit className="h-8 w-8 text-white" />;
  let title = 'Ready to train';
  let subtitle = 'No active model';
  let statusText = 'Idle';

  if (job) {
    switch (job.status) {
      case 'training':
      case 'pending':
        statusColor = 'from-blue-500 to-cyan-500';
        icon = <Loader2 className="h-8 w-8 animate-spin text-white" />;
        title = 'Training in progress';
        subtitle = 'Optimizing parameters...';
        statusText = job.status === 'pending' ? 'Queued' : 'Training';
        break;
      case 'completed':
        statusColor = 'from-violet-600 to-fuchsia-600';
        icon = <CheckCircle2 className="h-8 w-8 text-white" />;
        title = 'Model active';
        subtitle = 'Predictions enabled';
        statusText = 'Active';
        break;
      case 'failed':
        statusColor = 'from-rose-500 to-red-600';
        icon = <AlertTriangle className="h-8 w-8 text-white" />;
        title = 'Training failed';
        subtitle = 'Please try again';
        statusText = 'Failed';
        break;
    }
  }

  return (
    <motion.div
      whileHover={{ scale: 1.015 }}
      className={`group relative overflow-hidden rounded-[2rem] bg-gradient-to-br ${statusColor} p-6 text-white shadow-xl transition-all duration-300 hover:shadow-2xl`}
    >
      {/* Background decoration */}
      <div className="pointer-events-none absolute -right-6 -top-6 p-6 opacity-10 transition-opacity duration-500 group-hover:opacity-20">
        <BrainCircuit className="h-40 w-40" />
      </div>

      <div className="relative z-10 flex h-full flex-col justify-between">
        <div className="flex items-start justify-between">
          <div className="rounded-full bg-white/20 p-2 backdrop-blur-sm">{icon}</div>
          {job && (
            <div className="flex items-center gap-1.5 rounded-full bg-black/20 px-2.5 py-1 text-[10px] font-medium backdrop-blur-sm">
              <Clock className="h-3 w-3" />
              <span>{new Date(job.created_at).toLocaleDateString()}</span>
            </div>
          )}
        </div>

        <div className="mt-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-white/60">
              Model Status
            </span>
            <span className="rounded-full bg-white/20 px-2 py-0.5 text-[10px] font-bold uppercase">
              {statusText}
            </span>
          </div>

          <h3 className="text-2xl font-bold tracking-tight">{title}</h3>
          <p className="mt-1 text-sm font-medium text-white/70">{subtitle}</p>

          {/* Metrics Display */}
          {job?.status === 'completed' && job.metrics && (
            <div className="mt-4 grid grid-cols-3 gap-2 border-t border-white/10 pt-4">
              <div>
                <p className="text-[10px] font-medium text-white/60 uppercase">Val Loss</p>
                <p className="text-lg font-bold">{job.metrics.val_loss?.toFixed(2) || 'N/A'}</p>
              </div>
              <div>
                <p className="text-[10px] font-medium text-white/60 uppercase">Epochs</p>
                <p className="text-lg font-bold">{job.metrics.epochs_trained || '-'}</p>
              </div>
              <div>
                <p className="text-[10px] font-medium text-white/60 uppercase">Txns</p>
                <p className="text-lg font-bold">{job.metrics.transaction_count || '-'}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
