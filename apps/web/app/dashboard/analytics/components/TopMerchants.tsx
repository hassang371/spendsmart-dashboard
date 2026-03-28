'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Store } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildTopMerchants } from './analyticsUtils';

interface TopMerchantsProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

// Distinct palette per rank position (consistent with CategoryBreakdown)
const RANK_COLORS = [
  '#6366F1', // indigo
  '#F59E0B', // amber
  '#10B981', // emerald
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#8B5CF6', // violet
  '#F97316', // orange
  '#84CC16', // lime
];

export function TopMerchants({ transactions, isExpanded = false }: TopMerchantsProps) {
  const items = useMemo(
    () => buildTopMerchants(transactions, isExpanded ? 10 : 5),
    [transactions, isExpanded]
  );

  const totalSpend = useMemo(() => items.reduce((s, item) => s + item.amount, 0), [items]);

  if (items.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <Store className="h-8 w-8 opacity-20" />
        <p className="text-sm">No expense data in this period.</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative flex h-full w-full flex-col min-h-0"
    >
      <div className="mb-2 px-4 pt-2 shrink-0">
        <p className="text-xs font-semibold uppercase tracking-widest text-white/40">
          Top Merchants
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          ₹{Math.round(totalSpend).toLocaleString('en-IN')} · {items.length} merchants
        </p>
      </div>

      {/* Fill remaining height — rows share space equally */}
      <div className="flex flex-1 min-h-0 flex-col px-4 pb-3">
        {items.map((item, i) => (
          <motion.div
            key={item.merchant}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.055, duration: 0.32, ease: 'easeOut' }}
            className="flex flex-1 items-center gap-3 min-h-0 py-1"
          >
            {/* Rank */}
            <span
              className="w-5 shrink-0 text-center text-[10px] font-black tabular-nums"
              style={{ color: RANK_COLORS[i % RANK_COLORS.length] }}
            >
              {i + 1}
            </span>

            {/* Bar + label */}
            <div className="flex min-w-0 flex-1 flex-col justify-center gap-1">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-semibold text-white/80">
                  {item.merchant}
                </span>
                <div className="flex shrink-0 items-center gap-2">
                  <span
                    className="font-mono text-xs font-black"
                    style={{ color: RANK_COLORS[i % RANK_COLORS.length] }}
                  >
                    ₹{Math.round(item.amount).toLocaleString('en-IN')}
                  </span>
                  <span className="w-8 text-right text-[10px] font-bold text-white/25">
                    {Math.round(item.pct)}%
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-1 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ background: RANK_COLORS[i % RANK_COLORS.length] }}
                    initial={{ width: 0 }}
                    animate={{ width: `${item.pct}%` }}
                    transition={{ delay: i * 0.055 + 0.1, duration: 0.45, ease: 'easeOut' }}
                  />
                </div>
                <span className="shrink-0 text-[9px] font-medium text-white/20">
                  {item.count} {item.count === 1 ? 'txn' : 'txns'}
                </span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
