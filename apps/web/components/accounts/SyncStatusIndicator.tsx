'use client';

import { motion } from 'framer-motion';

interface SyncStatusIndicatorProps {
  status: 'idle' | 'syncing' | 'error';
  className?: string;
}

const configs = {
  idle: { color: 'bg-green-500', label: 'Synced', animate: false },
  syncing: { color: 'bg-blue-500', label: 'Syncing…', animate: true },
  error: { color: 'bg-red-500', label: 'Sync error', animate: false },
} as const;

export function SyncStatusIndicator({ status, className = '' }: SyncStatusIndicatorProps) {
  const cfg = configs[status];

  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <span className="relative flex h-2 w-2">
        {cfg.animate && (
          <motion.span
            className={`absolute inline-flex h-full w-full rounded-full ${cfg.color} opacity-75`}
            animate={{ scale: [1, 2, 1], opacity: [0.75, 0, 0.75] }}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
        )}
        <span className={`relative inline-flex h-2 w-2 rounded-full ${cfg.color}`} />
      </span>
      <span className="text-xs text-muted-foreground">{cfg.label}</span>
    </span>
  );
}
