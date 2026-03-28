'use client';

import { useMemo } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { motion } from 'framer-motion';
import { LineChart } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildCategoryTrendSeries } from './analyticsUtils';

interface CategoryTrendProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

// Distinct palette for up to 5 categories
const TREND_COLORS = [
  '#6366F1', // indigo
  '#F59E0B', // amber
  '#10B981', // green
  '#EC4899', // pink
  '#06B6D4', // cyan
];

export function CategoryTrend({ transactions, isExpanded = false }: CategoryTrendProps) {
  const { data, categories } = useMemo(
    () => buildCategoryTrendSeries(transactions),
    [transactions]
  );

  if (data.length === 0 || categories.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <LineChart className="h-8 w-8 opacity-20" />
        <p className="text-sm">Not enough data to show category trends.</p>
      </div>
    );
  }

  // Single month fallback
  if (data.length < 2) {
    const point = data[0];
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex h-full flex-col items-center justify-center gap-4 px-6"
      >
        <p className="text-xs font-semibold uppercase tracking-widest text-white/40">
          Category Trend ({point.month})
        </p>
        <div className="w-full flex flex-col gap-2">
          {categories.map((cat, i) => {
            const val = Number(point[cat] ?? 0);
            const max = Math.max(...categories.map(c => Number(point[c] ?? 0)), 1);
            return (
              <div key={cat} className="flex items-center gap-3">
                <span className="w-20 text-xs text-white/50 truncate">{cat}</span>
                <div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${(val / max) * 100}%`,
                      background: TREND_COLORS[i % TREND_COLORS.length],
                    }}
                  />
                </div>
                <span
                  className="w-20 text-right font-mono text-xs font-bold"
                  style={{ color: TREND_COLORS[i % TREND_COLORS.length] }}
                >
                  ₹{Math.round(val).toLocaleString('en-IN')}
                </span>
              </div>
            );
          })}
        </div>
        <p className="text-xs text-white/20">Add more months of data for trend view</p>
      </motion.div>
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
          Category Trend
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Top {categories.length} categories over time
        </p>
      </div>

      <div className={`flex-1 min-h-0 w-full ${isExpanded ? 'px-4 pb-6' : 'px-2 pb-3'}`}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              {categories.map((cat, i) => (
                <linearGradient key={cat} id={`grad-cat-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    stopColor={TREND_COLORS[i % TREND_COLORS.length]}
                    stopOpacity={0.35}
                  />
                  <stop
                    offset="100%"
                    stopColor={TREND_COLORS[i % TREND_COLORS.length]}
                    stopOpacity={0}
                  />
                </linearGradient>
              ))}
            </defs>
            <XAxis
              dataKey="month"
              tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10, fontWeight: 600 }}
              tickLine={false}
              axisLine={false}
              minTickGap={20}
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
            {categories.map((cat, i) => (
              <Area
                key={cat}
                type="monotone"
                dataKey={cat}
                stroke={TREND_COLORS[i % TREND_COLORS.length]}
                strokeWidth={2}
                fill={`url(#grad-cat-${i})`}
                stackId="1"
                activeDot={{ r: 5, strokeWidth: 0, fill: TREND_COLORS[i % TREND_COLORS.length] }}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
