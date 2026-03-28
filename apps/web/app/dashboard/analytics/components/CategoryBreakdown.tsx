'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { PieChart } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildCategoryBreakdown } from './analyticsUtils';

interface CategoryBreakdownProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

// Distinct palette per rank position
const CAT_COLORS = [
  '#6366F1', // indigo
  '#F59E0B', // amber
  '#10B981', // emerald
  '#EC4899', // pink
  '#06B6D4', // cyan
  '#8B5CF6', // violet
  '#F97316', // orange
  '#84CC16', // lime
];

export function CategoryBreakdown({ transactions, isExpanded = false }: CategoryBreakdownProps) {
  const items = useMemo(
    () => buildCategoryBreakdown(transactions, isExpanded ? 8 : 5),
    [transactions, isExpanded]
  );

  const totalExpense = useMemo(() => items.reduce((s, item) => s + item.amount, 0), [items]);

  if (items.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <PieChart className="h-8 w-8 opacity-20" />
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
      <div className="mb-3 px-4 pt-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-white/40">
          Top Spending Categories
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          ₹{Math.round(totalExpense).toLocaleString('en-IN')} total expenses
        </p>
      </div>

      <div
        className={`flex flex-col gap-2 overflow-y-auto no-scrollbar ${isExpanded ? 'px-4 pb-6' : 'px-4 pb-3'}`}
      >
        {items.map((item, i) => (
          <motion.div
            key={item.category}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.06, duration: 0.35, ease: 'easeOut' }}
            className="flex items-center gap-3"
          >
            {/* Rank */}
            <span
              className="w-5 shrink-0 text-center text-[10px] font-black tabular-nums"
              style={{ color: CAT_COLORS[i % CAT_COLORS.length] }}
            >
              {i + 1}
            </span>

            {/* Bar + label */}
            <div className="flex-1 min-w-0">
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="truncate text-xs font-semibold text-white/80">
                  {item.category}
                </span>
                <span
                  className="shrink-0 font-mono text-xs font-black"
                  style={{ color: CAT_COLORS[i % CAT_COLORS.length] }}
                >
                  ₹{Math.round(item.amount).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.05]">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: CAT_COLORS[i % CAT_COLORS.length] }}
                  initial={{ width: 0 }}
                  animate={{ width: `${item.pct}%` }}
                  transition={{ delay: i * 0.06 + 0.1, duration: 0.5, ease: 'easeOut' }}
                />
              </div>
            </div>

            {/* Percent */}
            <span className="w-9 shrink-0 text-right text-[10px] font-bold text-white/30">
              {Math.round(item.pct)}%
            </span>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
