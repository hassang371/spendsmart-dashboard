'use client';

import { useMemo } from 'react';
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { motion } from 'framer-motion';
import { Zap, CreditCard } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildRadarData } from './analyticsUtils';

interface SubscriptionLeakageRadarProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CustomAxisTick = ({ x, y, payload }: any) => (
  <text
    x={x}
    y={y}
    textAnchor="middle"
    dominantBaseline="central"
    fill="rgba(255,255,255,0.45)"
    fontSize={11}
    fontWeight={600}
    letterSpacing={0.5}
  >
    {payload.value}
  </text>
);

export function SubscriptionLeakageRadar({
  transactions,
  isExpanded = false,
}: SubscriptionLeakageRadarProps) {
  const radarData = useMemo(() => buildRadarData(transactions), [transactions]);

  const totalRecurring = radarData.reduce((s, r) => s + r.amount, 0);
  const hasData = totalRecurring > 0;

  // Recharts RadarChart expects an array of objects with a subject key + value key
  const chartData = radarData.map(r => ({
    subject: r.axis,
    amount: r.amount,
  }));

  // Max for normalisation — use raw amounts on tooltip, normalised on chart
  const maxVal = Math.max(...radarData.map(r => r.amount), 1);

  const normData = chartData.map(d => ({
    ...d,
    norm: maxVal > 0 ? Math.round((d.amount / maxVal) * 100) : 0,
  }));

  if (transactions.length === 0 || !hasData) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <Zap className="h-8 w-8 opacity-20" />
        <p className="text-sm">No recurring subscriptions detected.</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative flex h-full w-full flex-col min-h-0"
    >
      {/* Header metrics */}
      <div className="mb-3 flex items-center justify-between px-4 pt-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-white/40">
            Subscription Leakage
          </p>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span
              className="font-mono text-2xl font-black"
              style={{ color: '#EC4899', textShadow: '0 0 18px rgba(236,72,153,0.5)' }}
            >
              ₹{Math.round(totalRecurring).toLocaleString('en-IN')}
            </span>
            <span className="text-xs font-bold text-pink-500/70">/ period</span>
          </div>
        </div>
        {!isExpanded && (
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-pink-500/10">
            <Zap className="h-4 w-4 text-pink-500" />
          </div>
        )}
      </div>

      {isExpanded ? (
        <div className="flex flex-1 min-h-0 flex-col md:flex-row gap-6">
          {/* Radar chart */}
          <div className="w-full md:w-1/2 min-h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={normData} margin={{ top: 20, right: 30, bottom: 20, left: 30 }}>
                <PolarGrid gridType="polygon" stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
                <PolarAngleAxis dataKey="subject" tick={<CustomAxisTick />} />
                <Radar
                  name="Spend"
                  dataKey="norm"
                  stroke="#EC4899"
                  strokeWidth={2}
                  fill="#EC4899"
                  fillOpacity={0.15}
                  dot={{ fill: '#EC4899', r: 4, strokeWidth: 0 }}
                  activeDot={{
                    fill: '#EC4899',
                    r: 6,
                    strokeWidth: 0,
                    filter: 'drop-shadow(0 0 6px #EC4899)',
                  }}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const entry = payload[0].payload as { subject: string; amount: number };
                    return (
                      <div className="rounded-xl border border-white/[0.08] bg-black/80 px-3 py-2 text-xs backdrop-blur-md">
                        <p className="font-bold text-white">{entry.subject}</p>
                        <p className="text-pink-400 font-mono font-semibold mt-0.5">
                          ₹{Math.round(entry.amount).toLocaleString('en-IN')}
                        </p>
                      </div>
                    );
                  }}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Breakdown table */}
          <div className="w-full md:w-1/2 flex flex-col overflow-y-auto no-scrollbar gap-2">
            <h4 className="font-bold text-foreground mb-2 flex items-center gap-2 text-sm">
              <CreditCard className="h-4 w-4 text-muted-foreground" />
              By Category
            </h4>
            {radarData
              .filter(r => r.amount > 0)
              .sort((a, b) => b.amount - a.amount)
              .map(r => {
                const pct = totalRecurring > 0 ? (r.amount / totalRecurring) * 100 : 0;
                return (
                  <div
                    key={r.axis}
                    className="flex items-center gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-3"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="text-sm font-semibold text-foreground">{r.axis}</span>
                        <span className="font-mono text-sm font-black text-pink-400">
                          ₹{Math.round(r.amount).toLocaleString('en-IN')}
                        </span>
                      </div>
                      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/[0.06]">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-pink-600 to-pink-400"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>
      ) : (
        // Compact: radar chart only
        <div className="flex-1 min-h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={normData} margin={{ top: 16, right: 24, bottom: 16, left: 24 }}>
              <PolarGrid gridType="polygon" stroke="rgba(255,255,255,0.06)" strokeWidth={1} />
              <PolarAngleAxis dataKey="subject" tick={<CustomAxisTick />} />
              <Radar
                name="Spend"
                dataKey="norm"
                stroke="#EC4899"
                strokeWidth={2}
                fill="#EC4899"
                fillOpacity={0.18}
                dot={{ fill: '#EC4899', r: 3, strokeWidth: 0 }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const entry = payload[0].payload as { subject: string; amount: number };
                  return (
                    <div className="rounded-xl border border-white/[0.08] bg-black/80 px-3 py-2 text-xs backdrop-blur-md">
                      <p className="font-bold text-white">{entry.subject}</p>
                      <p className="text-pink-400 font-mono font-semibold mt-0.5">
                        ₹{Math.round(entry.amount).toLocaleString('en-IN')}
                      </p>
                    </div>
                  );
                }}
              />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
}
