'use client';

import { useMemo } from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  ReferenceLine,
} from 'recharts';
import { motion } from 'framer-motion';
import { BarChart2 } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildMonthlyBarData } from './analyticsUtils';

interface MonthOverMonthProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

export function MonthOverMonth({ transactions, isExpanded = false }: MonthOverMonthProps) {
  const data = useMemo(
    () => buildMonthlyBarData(transactions, isExpanded ? 12 : 6),
    [transactions, isExpanded]
  );

  if (data.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <BarChart2 className="h-8 w-8 opacity-20" />
        <p className="text-sm">Not enough data for comparison.</p>
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
          Month-over-Month
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">Income vs Expenses by month</p>
      </div>

      <div className={`flex-1 min-h-0 w-full ${isExpanded ? 'px-4 pb-6' : 'px-2 pb-3'}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            barGap={3}
            barCategoryGap="25%"
          >
            <XAxis
              dataKey="month"
              tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10, fontWeight: 600 }}
              tickLine={false}
              axisLine={false}
            />
            {isExpanded && (
              <YAxis
                tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`}
                tick={{ fill: 'rgba(255,255,255,0.2)', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={48}
              />
            )}
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(0,0,0,0.85)',
                borderColor: 'rgba(255,255,255,0.08)',
                borderRadius: '12px',
                backdropFilter: 'blur(12px)',
                fontSize: 12,
              }}
              formatter={(value: unknown) => [`₹${Number(value).toLocaleString('en-IN')}`, '']}
              itemStyle={{ color: 'rgba(255,255,255,0.8)', fontWeight: 600 }}
            />
            {isExpanded && (
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(val: string) => (
                  <span style={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600 }}>{val}</span>
                )}
              />
            )}
            <ReferenceLine y={0} stroke="rgba(255,255,255,0.08)" />
            <Bar
              dataKey="income"
              name="Income"
              fill="#10B981"
              radius={[3, 3, 0, 0]}
              opacity={0.9}
            />
            <Bar
              dataKey="expense"
              name="Expense"
              fill="#EF4444"
              radius={[3, 3, 0, 0]}
              opacity={0.9}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
