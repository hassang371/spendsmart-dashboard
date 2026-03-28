'use client';

import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { motion } from 'framer-motion';

interface Transaction {
  amount: number | string;
  transaction_date: string;
}

interface MonthlyComparisonProps {
  transactions: Transaction[];
  yearParam?: string;
  monthParam?: string;
  relativeParam?: string;
  isExpanded?: boolean;
}

export function MonthlyComparison({ transactions, isExpanded = false }: MonthlyComparisonProps) {
  const chartData = useMemo(() => {
    if (!transactions || transactions.length === 0) return [];

    const grouped = new Map<
      string,
      { dateStr: string; timestamp: number; income: number; expense: number }
    >();

    transactions.forEach(tx => {
      const d = new Date(tx.transaction_date);
      if (isNaN(d.getTime())) return;

      const dateKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      const amount = Number(tx.amount);

      if (!grouped.has(dateKey)) {
        grouped.set(dateKey, {
          dateStr: dateKey,
          timestamp: d.getTime(),
          income: 0,
          expense: 0,
        });
      }

      const entry = grouped.get(dateKey)!;
      if (amount > 0) {
        entry.income += amount;
      } else {
        entry.expense += Math.abs(amount);
      }
    });

    return Array.from(grouped.values())
      .sort((a, b) => a.timestamp - b.timestamp)
      .map(entry => ({
        date: new Date(entry.timestamp).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
        }),
        Income: entry.income,
        Expense: entry.expense,
      }));
  }, [transactions]);

  // Monthly regime computation for expanded Regime Shift strip
  const monthlyRegime = useMemo(() => {
    if (!isExpanded || !transactions.length) return [];
    const byMonth = new Map<string, { income: number; expense: number }>();
    transactions.forEach(tx => {
      const d = new Date(tx.transaction_date);
      if (isNaN(d.getTime())) return;
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      if (!byMonth.has(key)) byMonth.set(key, { income: 0, expense: 0 });
      const entry = byMonth.get(key)!;
      const amount = Number(tx.amount);
      if (amount > 0) entry.income += amount;
      else if (amount < 0) entry.expense += Math.abs(amount);
    });
    return Array.from(byMonth.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .slice(-12)
      .map(([key, { income, expense }]) => {
        const [year, month] = key.split('-').map(Number);
        const label = new Date(year, month - 1).toLocaleDateString('en-US', { month: 'short' });
        return { label, regime: income >= expense ? ('saving' as const) : ('spending' as const) };
      });
  }, [transactions, isExpanded]);

  if (chartData.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        No transaction data available for this range.
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex h-full w-full flex-col relative min-h-0"
    >
      {/* Chart Canvas */}
      <div className={`${isExpanded ? 'flex-1 min-h-0' : 'h-[300px]'} w-full relative pt-4`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorExpense" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#EF4444" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#EF4444" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              vertical={false}
              stroke="hsl(var(--border))"
              opacity={0.4}
            />
            <XAxis
              dataKey="date"
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              minTickGap={30}
            />
            {isExpanded && (
              <YAxis
                tickFormatter={val => `₹${(val / 1000).toFixed(0)}k`}
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={60}
              />
            )}
            <Tooltip
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                borderRadius: '12px',
                border: '1px solid hsl(var(--border))',
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)',
              }}
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              formatter={(value: any) => [`₹${Number(value).toLocaleString('en-IN')}`, '']}
            />
            <Area
              type="monotone"
              dataKey="Income"
              stroke="#10B981"
              strokeWidth={3}
              fillOpacity={1}
              fill="url(#colorIncome)"
              activeDot={{ r: 6, strokeWidth: 0, fill: '#10B981' }}
            />
            <Area
              type="monotone"
              dataKey="Expense"
              stroke="#EF4444"
              strokeWidth={3}
              fillOpacity={1}
              fill="url(#colorExpense)"
              activeDot={{ r: 6, strokeWidth: 0, fill: '#EF4444' }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Regime Shift strip — expanded only */}
      {isExpanded && monthlyRegime.length > 0 && (
        <div className="px-4 pb-4 pt-3 border-t border-white/[0.04]">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-white/30 mb-2">
            Regime Shifts
          </p>
          <div className="flex flex-wrap gap-1.5">
            {monthlyRegime.map(({ label, regime }) => (
              <div
                key={label}
                className={`flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ${
                  regime === 'saving'
                    ? 'bg-emerald-500/10 text-emerald-400'
                    : 'bg-red-500/10 text-red-400'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    regime === 'saving' ? 'bg-emerald-400' : 'bg-red-400'
                  }`}
                />
                {label}
              </div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
