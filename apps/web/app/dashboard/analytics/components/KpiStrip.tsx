'use client';

import { useMemo, useEffect, useRef } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus, Percent } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { computeKpis } from './analyticsUtils';

interface KpiCardProps {
  label: string;
  value: number;
  formatter: (n: number) => string;
  accent: string;
  glowColor: string;
  icon: React.ReactNode;
  delay: number;
  prefix?: string;
  suffix?: string;
}

function KpiCard({
  label,
  value,
  formatter,
  accent,
  glowColor,
  icon,
  delay,
  suffix,
}: KpiCardProps) {
  const motionVal = useMotionValue(0);
  const spring = useSpring(motionVal, { stiffness: 60, damping: 18 });
  const display = useTransform(spring, n => formatter(n));
  const prevValue = useRef(0);

  useEffect(() => {
    prevValue.current = 0;
    motionVal.set(0);
    const timer = setTimeout(() => motionVal.set(value), delay);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: delay / 1000, duration: 0.5, ease: 'easeOut' }}
      className="relative flex flex-col justify-between overflow-hidden rounded-2xl border border-white/[0.06] bg-white/[0.03] px-5 py-4 backdrop-blur-md"
      style={{ boxShadow: `inset 0 0 0 1px rgba(255,255,255,0.04)` }}
    >
      {/* Ambient glow behind number */}
      <div
        className="pointer-events-none absolute -bottom-4 -right-4 h-28 w-28 rounded-full opacity-20 blur-2xl"
        style={{ background: glowColor }}
      />

      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-widest text-white/40">
          {label}
        </span>
        <div
          className="flex h-7 w-7 items-center justify-center rounded-lg"
          style={{ background: `${glowColor}22` }}
        >
          <span style={{ color: accent }}>{icon}</span>
        </div>
      </div>

      <div className="flex items-baseline gap-1">
        <motion.span
          className="font-mono text-2xl font-black tracking-tight"
          style={{ color: accent, textShadow: `0 0 18px ${glowColor}66` }}
        >
          {display}
        </motion.span>
        {suffix && (
          <span className="text-sm font-bold" style={{ color: accent }}>
            {suffix}
          </span>
        )}
      </div>
    </motion.div>
  );
}

interface KpiStripProps {
  transactions: Transaction[];
}

export function KpiStrip({ transactions }: KpiStripProps) {
  const kpis = useMemo(() => computeKpis(transactions), [transactions]);

  const fmt = (n: number) => `₹${Math.round(Math.abs(n)).toLocaleString('en-IN')}`;

  const savingRateDisplay = (n: number) => `${Math.round(Math.abs(n))}`;

  const netIcon =
    kpis.netSavings > 0 ? (
      <TrendingUp className="h-3.5 w-3.5" />
    ) : kpis.netSavings < 0 ? (
      <TrendingDown className="h-3.5 w-3.5" />
    ) : (
      <Minus className="h-3.5 w-3.5" />
    );

  const netAccent = kpis.netSavings >= 0 ? '#10B981' : '#EF4444';
  const netGlow = kpis.netSavings >= 0 ? 'rgba(16,185,129,1)' : 'rgba(239,68,68,1)';

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      <KpiCard
        label="Total Income"
        value={kpis.totalIncome}
        formatter={fmt}
        accent="#10B981"
        glowColor="rgba(16,185,129,1)"
        icon={<TrendingUp className="h-3.5 w-3.5" />}
        delay={0}
      />
      <KpiCard
        label="Total Expenses"
        value={kpis.totalExpense}
        formatter={fmt}
        accent="#EF4444"
        glowColor="rgba(239,68,68,1)"
        icon={<TrendingDown className="h-3.5 w-3.5" />}
        delay={80}
      />
      <KpiCard
        label="Net Savings"
        value={Math.abs(kpis.netSavings)}
        formatter={fmt}
        accent={netAccent}
        glowColor={netGlow}
        icon={netIcon}
        delay={160}
      />
      <KpiCard
        label="Saving Rate"
        value={kpis.savingRate}
        formatter={savingRateDisplay}
        accent="#06B6D4"
        glowColor="rgba(6,182,212,1)"
        icon={<Percent className="h-3.5 w-3.5" />}
        delay={240}
        suffix="%"
      />
    </div>
  );
}
