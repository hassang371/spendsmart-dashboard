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

interface TooltipPayloadEntry {
  dataKey: string;
  name: string;
  value: number;
  fill: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;
  const income = payload.find(p => p.dataKey === 'income');
  const expense = payload.find(p => p.dataKey === 'expense');
  const net = (income?.value ?? 0) - (expense?.value ?? 0);
  return (
    <div className="rounded-xl border border-white/[0.1] bg-black/95 px-3.5 py-2.5 text-xs backdrop-blur-md shadow-2xl min-w-[160px]">
      <p className="mb-2 font-bold text-white/50 tracking-wide">{label}</p>
      {income && (
        <div className="flex items-center justify-between gap-4 mb-1">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            <span className="text-white/50">Income</span>
          </div>
          <span className="font-mono font-black text-emerald-400">
            ₹{Math.round(income.value).toLocaleString('en-IN')}
          </span>
        </div>
      )}
      {expense && (
        <div className="flex items-center justify-between gap-4 mb-1">
          <div className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-red-400" />
            <span className="text-white/50">Expense</span>
          </div>
          <span className="font-mono font-black text-red-400">
            ₹{Math.round(expense.value).toLocaleString('en-IN')}
          </span>
        </div>
      )}
      <div className="mt-2 border-t border-white/[0.06] pt-2 flex items-center justify-between gap-4">
        <span className="text-white/30">Net</span>
        <span className="font-mono font-black" style={{ color: net >= 0 ? '#10B981' : '#EF4444' }}>
          {net >= 0 ? '+' : ''}₹{Math.round(Math.abs(net)).toLocaleString('en-IN')}
        </span>
      </div>
    </div>
  );
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
            <Tooltip cursor={{ fill: 'rgba(255,255,255,0.03)' }} content={<CustomTooltip />} />
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
