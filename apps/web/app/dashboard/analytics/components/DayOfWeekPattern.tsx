'use client';

import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { motion } from 'framer-motion';
import { BarChart2 } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { computeDowAverages } from './analyticsUtils';

interface DayOfWeekPatternProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

export function DayOfWeekPattern({ transactions, isExpanded = false }: DayOfWeekPatternProps) {
  const data = useMemo(() => computeDowAverages(transactions), [transactions]);
  const hasData = data.some(d => d.average > 0);
  const peak = data.find(d => d.isPeak);

  if (!hasData) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <BarChart2 className="h-8 w-8 opacity-20" />
        <p className="text-sm">No spending data available.</p>
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
        <p className="text-xs font-semibold uppercase tracking-widest text-white/40">Day of Week</p>
        {peak && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            Peak: <span className="font-bold text-cyan-400">{peak.label}</span> avg ₹
            {Math.round(peak.average).toLocaleString('en-IN')}
          </p>
        )}
      </div>

      <div className={`flex-1 min-h-0 w-full ${isExpanded ? 'px-4 pb-6' : 'px-2 pb-3'}`}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            barCategoryGap="20%"
          >
            <XAxis
              dataKey="label"
              tick={{ fill: 'rgba(255,255,255,0.35)', fontSize: 11, fontWeight: 600 }}
              tickLine={false}
              axisLine={false}
            />
            {isExpanded && (
              <YAxis
                tickFormatter={v => `₹${(v / 1000).toFixed(0)}k`}
                tick={{ fill: 'rgba(255,255,255,0.25)', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={48}
              />
            )}
            <Tooltip
              cursor={{ fill: 'rgba(255,255,255,0.03)' }}
              content={({ active, payload, label }) => {
                if (!active || !payload?.length) return null;
                const val = payload[0].value as number;
                return (
                  <div className="rounded-xl border border-white/[0.08] bg-black/80 px-3 py-2 text-xs backdrop-blur-md">
                    <p className="font-bold text-white">{label}</p>
                    <p className="font-mono font-semibold text-cyan-400 mt-0.5">
                      ₹{Math.round(val).toLocaleString('en-IN')} avg
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="average" radius={[4, 4, 0, 0]} maxBarSize={32}>
              {data.map(entry => (
                <Cell
                  key={entry.label}
                  fill={entry.isPeak ? '#06B6D4' : 'rgba(255,255,255,0.12)'}
                  style={
                    entry.isPeak
                      ? { filter: 'drop-shadow(0 0 6px rgba(6,182,212,0.7))' }
                      : undefined
                  }
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
