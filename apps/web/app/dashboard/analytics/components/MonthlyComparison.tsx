'use client';

import { useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
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
    // Process transactions into chronological buckets
    if (!transactions || transactions.length === 0) return [];

    // Grouping by date string "YYYY-MM-DD" or similar basis depending on spread.
    // For simplicity and a smooth area chart, we'll sort chronologically and group by day.
    const grouped = new Map<string, { dateStr: string; timestamp: number; income: number; expense: number }>();

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
          expense: 0
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
        date: new Date(entry.timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
        Income: entry.income,
        Expense: entry.expense,
      }));
  }, [transactions]);

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
      className="flex h-full w-full flex-col relative"
    >
      {/* Chart Canvas */}
      <div className="flex-1 min-h-0 w-full relative pt-4">
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
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" opacity={0.4} />
            <XAxis
              dataKey="date"
              tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              minTickGap={30}
            />
            {isExpanded && (
              <YAxis
                tickFormatter={(val) => `₹${(val / 1000).toFixed(0)}k`}
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
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)'
              }}
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
    </motion.div>
  );
}
