/**
 * Pure data-transformation utilities for Analytics Phase 2 charts.
 * No React, no Recharts, no window/document — safe for SSR and unit tests.
 *
 * Sign convention: positive tx.amount = credit/income; negative = debit/expense.
 * Refs: docs/features/008-analytics-phase-2-advanced-charts.md
 */

import type { Transaction } from '../../../../lib/api/client';

// ─── KPI Strip ───────────────────────────────────────────────────────────────

export interface KpiResult {
  totalIncome: number;
  totalExpense: number;
  netSavings: number;
  /** 0–100, clamped. Returns 0 when totalIncome === 0. */
  savingRate: number;
}

export function computeKpis(transactions: Transaction[]): KpiResult {
  let totalIncome = 0;
  let totalExpense = 0;
  for (const tx of transactions) {
    const amount = Number(tx.amount);
    if (amount > 0) totalIncome += amount;
    else if (amount < 0) totalExpense += Math.abs(amount);
  }
  const netSavings = totalIncome - totalExpense;
  const rawRate = totalIncome > 0 ? (netSavings / totalIncome) * 100 : 0;
  const savingRate = Math.min(100, Math.max(-100, rawRate));
  return { totalIncome, totalExpense, netSavings, savingRate };
}

// ─── Subscription Leakage Radar ──────────────────────────────────────────────

export type SubscriptionAxis =
  | 'Entertainment'
  | 'Utilities'
  | 'SaaS'
  | 'Fitness'
  | 'Food Delivery'
  | 'Transport';

const AXIS_KEYWORDS: Record<SubscriptionAxis, string[]> = {
  Entertainment: [
    'netflix',
    'spotify',
    'disney',
    'hulu',
    'youtube premium',
    'apple tv',
    'prime video',
    'hotstar',
    'jio cinema',
    'zee5',
  ],
  Utilities: [
    'electricity',
    'water bill',
    'internet',
    'broadband',
    'gas',
    'bsnl',
    'airtel',
    'jio',
    'vi ',
  ],
  SaaS: [
    'aws',
    'adobe',
    'vercel',
    'github',
    'notion',
    'slack',
    'zoom',
    'figma',
    'linear',
    'atlassian',
  ],
  Fitness: ['gym', 'cult.fit', 'healthify', 'strava', 'fitpass', 'gold gym'],
  'Food Delivery': ['swiggy', 'zomato', 'swiggy one', 'zomato gold', 'blinkit', 'dunzo'],
  Transport: ['ola', 'uber', 'rapido', 'metro', 'irctc', 'redbus', 'yulu'],
};

export function mapSubscriptionToAxis(description: string): SubscriptionAxis | null {
  const lower = description.toLowerCase();
  for (const [axis, keywords] of Object.entries(AXIS_KEYWORDS) as [SubscriptionAxis, string[]][]) {
    if (keywords.some(k => lower.includes(k))) return axis;
  }
  return null;
}

export interface RadarAxisData {
  axis: SubscriptionAxis;
  amount: number;
}

export function buildRadarData(transactions: Transaction[]): RadarAxisData[] {
  const totals: Record<SubscriptionAxis, number> = {
    Entertainment: 0,
    Utilities: 0,
    SaaS: 0,
    Fitness: 0,
    'Food Delivery': 0,
    Transport: 0,
  };
  for (const tx of transactions) {
    const amount = Number(tx.amount);
    if (amount >= 0) continue;
    const axis = mapSubscriptionToAxis(tx.description);
    if (axis) totals[axis] += Math.abs(amount);
  }
  return (Object.keys(totals) as SubscriptionAxis[]).map(axis => ({
    axis,
    amount: totals[axis],
  }));
}

// ─── Spend Heatmap ───────────────────────────────────────────────────────────

export interface HeatmapCell {
  /** YYYY-MM-DD */
  date: string;
  amount: number;
  /** 0-indexed calendar week row (0 = oldest) */
  week: number;
  /** 0 = Monday … 6 = Sunday */
  dow: number;
}

export interface MonthLabel {
  label: string;
  weekIndex: number;
}

export interface HeatmapGrid {
  cells: HeatmapCell[];
  maxAmount: number;
  weeks: number;
  monthLabels: MonthLabel[];
}

/**
 * Builds a calendar heatmap grid from transactions.
 * Caps at maxWeeks most-recent weeks (default 52).
 */
export function buildHeatmapGrid(transactions: Transaction[], maxWeeks = 52): HeatmapGrid {
  // Aggregate expense amounts by date
  const byDate = new Map<string, number>();
  for (const tx of transactions) {
    const amount = Number(tx.amount);
    if (amount >= 0) continue;
    const d = new Date(tx.transaction_date);
    if (isNaN(d.getTime())) continue;
    const key = d.toISOString().slice(0, 10);
    byDate.set(key, (byDate.get(key) ?? 0) + Math.abs(amount));
  }

  if (byDate.size === 0) {
    return { cells: [], maxAmount: 0, weeks: 0, monthLabels: [] };
  }

  // Determine range
  const allDates = Array.from(byDate.keys()).sort();
  const rawEnd = new Date(allDates[allDates.length - 1]);
  // Align start to the Monday of the week containing rawEnd - maxWeeks*7 days
  const rawStart = new Date(rawEnd);
  rawStart.setDate(rawEnd.getDate() - maxWeeks * 7 + 1);
  // Roll back rawStart to the Monday of that week
  const startDow = (rawStart.getDay() + 6) % 7; // 0=Mon
  rawStart.setDate(rawStart.getDate() - startDow);

  // Walk days from rawStart to rawEnd
  const cells: HeatmapCell[] = [];
  const monthsSeen = new Map<string, number>();
  let maxAmount = 0;
  let weekIndex = 0;

  const cursor = new Date(rawStart);
  while (cursor <= rawEnd) {
    const key = cursor.toISOString().slice(0, 10);
    const dow = (cursor.getDay() + 6) % 7; // 0=Mon

    if (dow === 0 && cursor > rawStart) weekIndex++;

    const amount = byDate.get(key) ?? 0;
    if (amount > maxAmount) maxAmount = amount;

    cells.push({ date: key, amount, week: weekIndex, dow });

    // Track month labels (first Monday of each new month)
    const monthKey = `${cursor.getFullYear()}-${cursor.getMonth()}`;
    if (dow === 0 && !monthsSeen.has(monthKey)) {
      monthsSeen.set(monthKey, weekIndex);
    }

    cursor.setDate(cursor.getDate() + 1);
  }

  const monthLabels: MonthLabel[] = Array.from(monthsSeen.entries()).map(([key, wi]) => {
    const [year, month] = key.split('-').map(Number);
    const d = new Date(year, month, 1);
    return {
      label: d.toLocaleDateString('en-US', { month: 'short' }),
      weekIndex: wi,
    };
  });

  return { cells, maxAmount, weeks: weekIndex + 1, monthLabels };
}

// ─── Day-of-Week Pattern ─────────────────────────────────────────────────────

export interface DowAverage {
  /** 0 = Monday … 6 = Sunday */
  dow: number;
  label: string;
  average: number;
  isPeak: boolean;
}

const DOW_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function computeDowAverages(transactions: Transaction[]): DowAverage[] {
  const sums = new Array<number>(7).fill(0);
  const counts = new Array<number>(7).fill(0);

  for (const tx of transactions) {
    const amount = Number(tx.amount);
    if (amount >= 0) continue;
    const d = new Date(tx.transaction_date);
    if (isNaN(d.getTime())) continue;
    const dow = (d.getDay() + 6) % 7; // 0=Mon
    sums[dow] += Math.abs(amount);
    counts[dow]++;
  }

  const averages = sums.map((s, i) => (counts[i] > 0 ? s / counts[i] : 0));
  const peak = Math.max(...averages);

  return DOW_LABELS.map((label, i) => ({
    dow: i,
    label,
    average: averages[i],
    isPeak: peak > 0 && averages[i] === peak,
  }));
}

// ─── Category Trend ──────────────────────────────────────────────────────────

export interface CategoryTrendPoint {
  month: string;
  [category: string]: number | string;
}

export interface CategoryTrendSeries {
  data: CategoryTrendPoint[];
  /** Top categories, ordered by total spend descending */
  categories: string[];
}

export function buildCategoryTrendSeries(transactions: Transaction[]): CategoryTrendSeries {
  // Group expenses by (YYYY-MM, category)
  const byMonthCat = new Map<string, Map<string, number>>();
  const categoryTotals = new Map<string, number>();

  for (const tx of transactions) {
    const amount = Number(tx.amount);
    if (amount >= 0) continue;
    const d = new Date(tx.transaction_date);
    if (isNaN(d.getTime())) continue;
    const monthKey = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    const cat = tx.category || 'Uncategorized';
    const absAmount = Math.abs(amount);

    if (!byMonthCat.has(monthKey)) byMonthCat.set(monthKey, new Map());
    const catMap = byMonthCat.get(monthKey)!;
    catMap.set(cat, (catMap.get(cat) ?? 0) + absAmount);

    categoryTotals.set(cat, (categoryTotals.get(cat) ?? 0) + absAmount);
  }

  if (byMonthCat.size === 0) return { data: [], categories: [] };

  // Top 5 categories by total spend in the filtered range
  const categories = Array.from(categoryTotals.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([cat]) => cat);

  // Build month-sorted data points
  const sortedMonths = Array.from(byMonthCat.keys()).sort();
  const data: CategoryTrendPoint[] = sortedMonths.map(mk => {
    const [year, month] = mk.split('-').map(Number);
    const d = new Date(year, month - 1, 1);
    const label = d.toLocaleDateString('en-US', { month: 'short', year: '2-digit' });
    const point: CategoryTrendPoint = { month: label };
    const catMap = byMonthCat.get(mk)!;
    for (const cat of categories) {
      point[cat] = catMap.get(cat) ?? 0;
    }
    return point;
  });

  return { data, categories };
}
