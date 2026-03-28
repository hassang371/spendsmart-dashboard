'use client';

import { useMemo, useState, useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { CalendarDays } from 'lucide-react';
import { type Transaction } from '../../../../lib/api/client';
import { buildHeatmapGrid } from './analyticsUtils';

interface SpendHeatmapProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

const DOW_LABELS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];
const LABEL_W = 18; // space for dow labels
const LABEL_H = 18; // space for month labels
const CELL_GAP = 2;

/** Interpolate from near-transparent to pink-500 based on intensity 0–1 */
function cellColor(intensity: number): string {
  if (intensity <= 0) return 'rgba(255,255,255,0.05)';
  const r = Math.round(236 * intensity);
  const g = Math.round(72 * intensity);
  const b = Math.round(153 * intensity);
  const a = 0.2 + intensity * 0.75;
  return `rgba(${r},${g},${b},${a})`;
}

interface TooltipState {
  date: string;
  amount: number;
  cx: number;
  cy: number;
}

export function SpendHeatmap({ transactions, isExpanded = false }: SpendHeatmapProps) {
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const update = () => setContainerWidth(el.getBoundingClientRect().width);
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const maxWeeks = isExpanded ? 52 : 26;
  const grid = useMemo(() => buildHeatmapGrid(transactions, maxWeeks), [transactions, maxWeeks]);

  // Compute cell size from container width so cells always fill available space
  const weeks = grid.weeks || 1;
  const rawCellSize =
    containerWidth > 0
      ? Math.floor((containerWidth - LABEL_W - CELL_GAP * (weeks + 1)) / weeks)
      : 14;
  const cellSize = Math.max(8, rawCellSize);
  const step = cellSize + CELL_GAP;
  const svgWidth = LABEL_W + weeks * step;
  const svgHeight = LABEL_H + 7 * step;

  if (grid.cells.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-muted-foreground">
        <CalendarDays className="h-8 w-8 opacity-20" />
        <p className="text-sm">No expense data in this period.</p>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative flex h-full w-full flex-col min-h-0"
    >
      <div className="mb-2 px-4 pt-2">
        <p className="text-xs font-semibold uppercase tracking-widest text-white/40">
          Daily Spend Intensity
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground">{grid.weeks}w • darker = more spent</p>
      </div>

      {/* SVG container — fills full width via ref */}
      <div ref={containerRef} className="flex-1 min-h-0 w-full px-4">
        {containerWidth > 0 && (
          <svg
            width={svgWidth}
            height={svgHeight}
            style={{ display: 'block', overflow: 'visible' }}
          >
            {/* Month labels */}
            {grid.monthLabels.map(ml => (
              <text
                key={`${ml.label}-${ml.weekIndex}`}
                x={LABEL_W + ml.weekIndex * step}
                y={12}
                fill="rgba(255,255,255,0.35)"
                fontSize={Math.max(9, Math.min(11, cellSize * 0.4))}
                fontWeight={600}
              >
                {ml.label}
              </text>
            ))}

            {/* Day-of-week labels (only M, W, F, S) */}
            {DOW_LABELS.map((d, i) => (
              <text
                key={i}
                x={LABEL_W / 2}
                y={LABEL_H + i * step + cellSize / 2 + 1}
                fill="rgba(255,255,255,0.2)"
                fontSize={Math.max(7, Math.min(10, cellSize * 0.4))}
                fontWeight={700}
                textAnchor="middle"
                dominantBaseline="central"
              >
                {i % 2 === 0 ? d : ''}
              </text>
            ))}

            {/* Heatmap cells */}
            {grid.cells.map(cell => {
              const intensity = grid.maxAmount > 0 ? cell.amount / grid.maxAmount : 0;
              const cx = LABEL_W + cell.week * step;
              const cy = LABEL_H + cell.dow * step;
              const r = Math.max(2, cellSize * 0.2);
              return (
                <rect
                  key={cell.date}
                  x={cx}
                  y={cy}
                  width={cellSize}
                  height={cellSize}
                  rx={r}
                  fill={cellColor(intensity)}
                  style={{ cursor: cell.amount > 0 ? 'pointer' : 'default' }}
                  onMouseEnter={() => {
                    if (cell.amount > 0) {
                      setTooltip({ date: cell.date, amount: cell.amount, cx, cy });
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
                  x={tooltip.cx - 50}
                  y={tooltip.cy - 32}
                  width={100 + (cellSize > 16 ? cellSize - 8 : 0)}
                  height={28}
                  rx={6}
                  fill="rgba(0,0,0,0.9)"
                  stroke="rgba(236,72,153,0.4)"
                  strokeWidth={1}
                />
                <text
                  x={tooltip.cx + cellSize / 2}
                  y={tooltip.cy - 20}
                  textAnchor="middle"
                  fill="rgba(255,255,255,0.65)"
                  fontSize={9}
                  fontWeight={600}
                >
                  {new Date(tooltip.date).toLocaleDateString('en-US', {
                    day: 'numeric',
                    month: 'short',
                  })}
                </text>
                <text
                  x={tooltip.cx + cellSize / 2}
                  y={tooltip.cy - 9}
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
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-2 px-4 pb-3 pt-1">
        <span className="text-[10px] text-white/25 font-medium">Less</span>
        {[0, 0.25, 0.5, 0.75, 1].map(v => (
          <div
            key={v}
            className="rounded-sm"
            style={{
              width: Math.max(8, Math.min(12, cellSize * 0.5)),
              height: Math.max(8, Math.min(12, cellSize * 0.5)),
              background: cellColor(v),
            }}
          />
        ))}
        <span className="text-[10px] text-white/25 font-medium">More</span>
      </div>
    </motion.div>
  );
}
