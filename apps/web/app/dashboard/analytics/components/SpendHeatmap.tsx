'use client';

import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { CalendarDays } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildHeatmapGrid } from './analyticsUtils';

interface SpendHeatmapProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

const CELL_SIZE = 13;
const CELL_GAP = 2;
const STEP = CELL_SIZE + CELL_GAP;
const DOW_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

/** Interpolate from #0A0A0A→transparent to #EC4899 based on intensity 0–1 */
function cellColor(intensity: number): string {
  if (intensity <= 0) return 'rgba(255,255,255,0.04)';
  // Gradient: low → pink-900 → pink-500
  const r = Math.round(236 * intensity);
  const g = Math.round(72 * intensity);
  const b = Math.round(153 * intensity);
  const a = 0.2 + intensity * 0.75;
  return `rgba(${r},${g},${b},${a})`;
}

interface TooltipState {
  date: string;
  amount: number;
  x: number;
  y: number;
}

export function SpendHeatmap({ transactions, isExpanded = false }: SpendHeatmapProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);

  const maxWeeks = isExpanded ? 52 : 26;
  const grid = useMemo(() => buildHeatmapGrid(transactions, maxWeeks), [transactions, maxWeeks]);

  if (grid.cells.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <CalendarDays className="h-8 w-8 opacity-20" />
        <p className="text-sm">No expense data in this period.</p>
      </div>
    );
  }

  const svgWidth = grid.weeks * STEP + 28; // +28 for dow labels
  const svgHeight = 7 * STEP + 22; // +22 for month labels

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative flex h-full w-full flex-col min-h-0"
    >
      <div className="mb-3 px-4 pt-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-white/40">
          Daily Spend Intensity
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">{grid.weeks}w • darker = more spent</p>
      </div>

      <div className="flex-1 min-h-0 overflow-x-auto overflow-y-hidden px-4 pb-4 no-scrollbar">
        <svg width={svgWidth} height={svgHeight} style={{ display: 'block', minWidth: svgWidth }}>
          {/* Month labels */}
          {grid.monthLabels.map(ml => (
            <text
              key={`${ml.label}-${ml.weekIndex}`}
              x={28 + ml.weekIndex * STEP}
              y={12}
              fill="rgba(255,255,255,0.3)"
              fontSize={10}
              fontWeight={600}
            >
              {ml.label}
            </text>
          ))}

          {/* Day-of-week labels */}
          {DOW_LABELS.map((d, i) => (
            <text
              key={i}
              x={10}
              y={22 + i * STEP + CELL_SIZE / 2 + 1}
              fill="rgba(255,255,255,0.2)"
              fontSize={9}
              fontWeight={700}
              textAnchor="middle"
              dominantBaseline="central"
            >
              {i % 2 === 0 ? d : ''}
            </text>
          ))}

          {/* Heatmap cells */}
          {grid.cells.map((cell, idx) => {
            const intensity = grid.maxAmount > 0 ? cell.amount / grid.maxAmount : 0;
            const cx = 28 + cell.week * STEP;
            const cy = 22 + cell.dow * STEP;
            return (
              <motion.rect
                key={cell.date}
                x={cx}
                y={cy}
                width={CELL_SIZE}
                height={CELL_SIZE}
                rx={3}
                fill={cellColor(intensity)}
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: idx * 0.001, duration: 0.25 }}
                style={{ cursor: cell.amount > 0 ? 'pointer' : 'default' }}
                onMouseEnter={_e => {
                  if (cell.amount > 0) {
                    setTooltip({
                      date: cell.date,
                      amount: cell.amount,
                      x: cx + CELL_SIZE / 2,
                      y: cy - 6,
                    });
                  }
                }}
                onMouseLeave={() => setTooltip(null)}
              />
            );
          })}

          {/* Tooltip */}
          {tooltip && (
            <g>
              <rect
                x={tooltip.x - 54}
                y={tooltip.y - 28}
                width={108}
                height={26}
                rx={6}
                fill="rgba(0,0,0,0.9)"
                stroke="rgba(236,72,153,0.4)"
                strokeWidth={1}
              />
              <text
                x={tooltip.x}
                y={tooltip.y - 18}
                textAnchor="middle"
                fill="rgba(255,255,255,0.7)"
                fontSize={9}
                fontWeight={600}
              >
                {new Date(tooltip.date).toLocaleDateString('en-US', {
                  day: 'numeric',
                  month: 'short',
                })}
              </text>
              <text
                x={tooltip.x}
                y={tooltip.y - 7}
                textAnchor="middle"
                fill="#EC4899"
                fontSize={10}
                fontWeight={800}
                fontFamily="monospace"
              >
                ₹{Math.round(tooltip.amount).toLocaleString('en-IN')}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 px-4 pb-3">
        <span className="text-[10px] text-white/25 font-medium">Less</span>
        {[0, 0.25, 0.5, 0.75, 1].map(v => (
          <div key={v} className="h-2.5 w-2.5 rounded-sm" style={{ background: cellColor(v) }} />
        ))}
        <span className="text-[10px] text-white/25 font-medium">More</span>
      </div>
    </motion.div>
  );
}
