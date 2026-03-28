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
  CartesianGrid,
  Cell,
} from 'recharts';
import { motion } from 'framer-motion';
import { BarChart2 } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildMonthlyBarData } from './analyticsUtils';

interface MonthOverMonthProps {
  /** Pass the full unfiltered transaction set so the chart always shows historical months. */
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
        <p className="mt-0.5 text-xs text-muted-foreground">
          Historical income vs expenses — last {isExpanded ? 12 : 6} months
        </p>
      </div>

      <div className={`flex-1 min-h-0 w-full ${isExpanded ? 'px-4 pb-6' : 'px-2 pb-3'}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            barGap={3}
            barCategoryGap="28%"
            style={{ background: 'transparent' }}
          >
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.04)" />
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
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
              contentStyle={{
                backgroundColor: 'rgba(10,10,10,0.95)',
                borderColor: 'rgba(255,255,255,0.08)',
                borderRadius: '12px',
                backdropFilter: 'blur(12px)',
                fontSize: 12,
                boxShadow: '0 8px 32px rgba(0,0,0,0.6)',
              }}
              labelStyle={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600, marginBottom: 4 }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: unknown, name: any) => [
                `₹${Number(value).toLocaleString('en-IN')}`,
                name as string,
              ]}
              itemStyle={{ fontWeight: 700 }}
            />
            {isExpanded && (
              <Legend
                wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
                formatter={(val: string) => (
                  <span style={{ color: 'rgba(255,255,255,0.5)', fontWeight: 600 }}>{val}</span>
                )}
              />
            )}
            <Bar dataKey="income" name="Income" radius={[3, 3, 0, 0]} background={false}>
              {data.map((_, i) => (
                <Cell key={i} fill="#10B981" fillOpacity={0.9} />
              ))}
            </Bar>
            <Bar dataKey="expense" name="Expense" radius={[3, 3, 0, 0]} background={false}>
              {data.map((_, i) => (
                <Cell key={i} fill="#EF4444" fillOpacity={0.9} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
