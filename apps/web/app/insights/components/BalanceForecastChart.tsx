'use client';

import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ForecastPoint } from '@/lib/api/forecast.types';

interface BalanceForecastChartProps {
  forecast: ForecastPoint[];
  /** Today's date as YYYY-MM-DD; reserved for a vertical reference marker. */
  today?: string;
}

interface FanRow {
  date: string;
  outerLow: number;
  outerHigh: number;
  midLow: number;
  midHigh: number;
  innerLow: number;
  innerHigh: number;
  p2: number;
  p10: number;
  p25: number;
  p50: number;
  p75: number;
  p90: number;
  p98: number;
  outerBand: [number, number];
  midBand: [number, number];
  innerBand: [number, number];
}

function pointsToRows(points: ForecastPoint[]): FanRow[] {
  return points.map(p => ({
    date: p.date,
    outerLow: p.p2,
    outerHigh: p.p98,
    midLow: p.p10,
    midHigh: p.p90,
    innerLow: p.p25,
    innerHigh: p.p75,
    p2: p.p2,
    p10: p.p10,
    p25: p.p25,
    p50: p.p50,
    p75: p.p75,
    p90: p.p90,
    p98: p.p98,
    outerBand: [p.p2, p.p98],
    midBand: [p.p10, p.p90],
    innerBand: [p.p25, p.p75],
  }));
}

const inrFormatter = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  maximumFractionDigits: 0,
});

interface TooltipPayload {
  payload?: FanRow;
}

interface TooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
}

function FanTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="rounded-md border border-border bg-card p-3 text-xs shadow-md">
      <p className="mb-2 font-semibold">{label}</p>
      <ul className="space-y-0.5 tabular-nums">
        <li>P98: {inrFormatter.format(row.p98)}</li>
        <li>P90: {inrFormatter.format(row.p90)}</li>
        <li>P75: {inrFormatter.format(row.p75)}</li>
        <li className="font-semibold">P50: {inrFormatter.format(row.p50)}</li>
        <li>P25: {inrFormatter.format(row.p25)}</li>
        <li>P10: {inrFormatter.format(row.p10)}</li>
        <li>P2: {inrFormatter.format(row.p2)}</li>
      </ul>
    </div>
  );
}

/** Per LLD 011 §BalanceForecastChart — recharts fan chart with three bands. */
export default function BalanceForecastChart({ forecast }: BalanceForecastChartProps) {
  if (!forecast || forecast.length === 0) {
    return (
      <section
        data-testid="balance-forecast-chart"
        className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
      >
        <h2 className="text-sm font-medium text-muted-foreground">Balance forecast</h2>
        <p className="mt-3 text-sm text-muted-foreground">No forecast data available.</p>
      </section>
    );
  }

  // Defensive: detect a quantile-ordering violation. Should not happen because
  // RFC-003's Pydantic model validates it, but we render P50-only if so.
  const orderingOk = forecast.every(
    p =>
      p.p2 <= p.p10 &&
      p.p10 <= p.p25 &&
      p.p25 <= p.p50 &&
      p.p50 <= p.p75 &&
      p.p75 <= p.p90 &&
      p.p90 <= p.p98
  );
  const rows = pointsToRows(forecast);

  return (
    <section
      data-testid="balance-forecast-chart"
      aria-labelledby="balance-forecast-heading"
      className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
    >
      <h2 id="balance-forecast-heading" className="text-sm font-medium text-muted-foreground">
        Balance forecast
      </h2>
      <div className="mt-4 h-64 w-full" data-testid="balance-forecast-chart-canvas">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={24} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={v => inrFormatter.format(v)} width={80} />
            <Tooltip content={<FanTooltip />} />
            <Legend wrapperStyle={{ fontSize: '12px' }} />
            {orderingOk && (
              <>
                <Area
                  type="monotone"
                  dataKey="outerBand"
                  name="P2–P98"
                  stroke="none"
                  fill="hsl(var(--primary))"
                  fillOpacity={0.15}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="midBand"
                  name="P10–P90"
                  stroke="none"
                  fill="hsl(var(--primary))"
                  fillOpacity={0.3}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="innerBand"
                  name="P25–P75"
                  stroke="none"
                  fill="hsl(var(--primary))"
                  fillOpacity={0.5}
                  isAnimationActive={false}
                />
              </>
            )}
            <Line
              type="monotone"
              dataKey="p50"
              name="P50"
              stroke="hsl(var(--primary))"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
