'use client';

import { useMemo, useEffect } from 'react';
import { motion, useMotionValue, useSpring, useTransform } from 'framer-motion';
import { type Transaction } from '../../../../lib/api/client';
import { computeKpis } from './analyticsUtils';

interface SavingsRateGaugeProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

// Full arc: 135° → 405° (= 45°), sweeping 270° clockwise
const CX = 100;
const CY = 100;
const R = 68;
const START_DEG = 135;
const SWEEP_DEG = 270;
// Arc length = (270/360) * 2π * 68
const TOTAL_ARC = (SWEEP_DEG / 360) * 2 * Math.PI * R; // ≈ 320.4

function toRad(deg: number) {
  return (deg * Math.PI) / 180;
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number): string {
  const x1 = cx + r * Math.cos(toRad(startDeg));
  const y1 = cy + r * Math.sin(toRad(startDeg));
  const x2 = cx + r * Math.cos(toRad(endDeg));
  const y2 = cy + r * Math.sin(toRad(endDeg));
  const largeArc = endDeg - startDeg > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
}

const TRACK_PATH = arcPath(CX, CY, R, START_DEG, START_DEG + SWEEP_DEG);

export function SavingsRateGauge({ transactions, isExpanded = false }: SavingsRateGaugeProps) {
  const { savingRate } = useMemo(() => computeKpis(transactions), [transactions]);

  const motionRate = useMotionValue(0);
  const spring = useSpring(motionRate, { stiffness: 45, damping: 18 });
  const displayRate = useTransform(spring, n => `${Math.round(Math.abs(n))}`);

  // Animate dashoffset based on spring value
  const dashOffset = useTransform(spring, n => {
    const clamped = Math.max(-100, Math.min(100, n));
    const pct = Math.max(0, clamped) / 100;
    return TOTAL_ARC * (1 - pct);
  });

  useEffect(() => {
    motionRate.set(0);
    const t = setTimeout(() => motionRate.set(savingRate), 350);
    return () => clearTimeout(t);
  }, [savingRate, motionRate]);

  const color = savingRate >= 30 ? '#10B981' : savingRate >= 10 ? '#F59E0B' : '#EF4444';
  const glowRgb = savingRate >= 30 ? '16,185,129' : savingRate >= 10 ? '245,158,11' : '239,68,68';
  const statusLabel = savingRate >= 30 ? 'Healthy' : savingRate >= 10 ? 'Moderate' : 'At Risk';

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative flex h-full w-full flex-col items-center justify-center min-h-0 gap-1"
    >
      <p className="text-xs font-semibold uppercase tracking-widest text-white/40">Saving Rate</p>

      <div className="relative" style={{ filter: `drop-shadow(0 0 24px rgba(${glowRgb},0.35))` }}>
        <svg width={isExpanded ? 220 : 190} height={isExpanded ? 220 : 190} viewBox="0 0 200 200">
          {/* Gradient defs */}
          <defs>
            <linearGradient id="gauge-fill-grad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor={color} stopOpacity={0.6} />
              <stop offset="100%" stopColor={color} stopOpacity={1} />
            </linearGradient>
            <filter id="gauge-glow">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Track */}
          <path
            d={TRACK_PATH}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={14}
            strokeLinecap="round"
          />

          {/* Filled arc — animated via framer-motion */}
          <motion.path
            d={TRACK_PATH}
            fill="none"
            stroke={`url(#gauge-fill-grad)`}
            strokeWidth={14}
            strokeLinecap="round"
            strokeDasharray={TOTAL_ARC}
            style={{ strokeDashoffset: dashOffset }}
            filter="url(#gauge-glow)"
          />

          {/* Center: rate value */}
          <text
            x={CX}
            y={CY - 10}
            textAnchor="middle"
            dominantBaseline="central"
            fill={color}
            fontSize={34}
            fontWeight={900}
            fontFamily="monospace"
            style={{ letterSpacing: '-2px' }}
          >
            <motion.tspan>{displayRate}</motion.tspan>
          </text>

          {/* % sign */}
          <text
            x={CX}
            y={CY + 16}
            textAnchor="middle"
            fill="rgba(255,255,255,0.25)"
            fontSize={13}
            fontWeight={700}
          >
            %
          </text>

          {/* Status label */}
          <text
            x={CX}
            y={CY + 34}
            textAnchor="middle"
            fill={color}
            fontSize={11}
            fontWeight={800}
            letterSpacing={1.5}
            style={{ textTransform: 'uppercase' }}
          >
            {statusLabel}
          </text>

          {/* Scale ticks at 0%, 50%, 100% */}
          {[0, 0.5, 1].map(pct => {
            const deg = START_DEG + pct * SWEEP_DEG;
            const innerR = R - 10;
            const outerR = R + 6;
            const x1 = CX + innerR * Math.cos(toRad(deg));
            const y1 = CY + innerR * Math.sin(toRad(deg));
            const x2 = CX + outerR * Math.cos(toRad(deg));
            const y2 = CY + outerR * Math.sin(toRad(deg));
            return (
              <line
                key={pct}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke="rgba(255,255,255,0.15)"
                strokeWidth={1.5}
                strokeLinecap="round"
              />
            );
          })}
        </svg>
      </div>

      {/* Legend row */}
      {isExpanded ? (
        <div className="flex gap-5 mt-1">
          {[
            { label: '≥ 30%', note: 'Healthy', color: '#10B981' },
            { label: '10–29%', note: 'Moderate', color: '#F59E0B' },
            { label: '< 10%', note: 'At Risk', color: '#EF4444' },
          ].map(t => (
            <div key={t.note} className="text-center">
              <p className="text-[10px] text-white/25 font-medium">{t.label}</p>
              <p className="text-xs font-bold" style={{ color: t.color }}>
                {t.note}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-[10px] text-white/25 font-medium">of income saved</p>
      )}
    </motion.div>
  );
}
