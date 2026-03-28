/**
 * Unit tests for Analytics Phase 2 pure utility functions.
 * Refs: docs/features/008-analytics-phase-2-advanced-charts.md
 */

import { describe, it, expect } from 'vitest';
import type { Transaction } from '../lib/api/client';
import {
  computeKpis,
  mapSubscriptionToAxis,
  buildRadarData,
  buildHeatmapGrid,
  computeDowAverages,
  buildCategoryTrendSeries,
  buildMonthlyBarData,
  buildCategoryBreakdown,
  buildTopMerchants,
} from '../app/dashboard/analytics/components/analyticsUtils';

// ─── Helpers ─────────────────────────────────────────────────────────────────

function tx(
  overrides: Partial<Transaction> & { amount: number; transaction_date: string }
): Transaction {
  return {
    id: 'test-id',
    user_id: 'user-1',
    currency: 'INR',
    description: 'Test',
    merchant_name: 'Test Merchant',
    category: 'Other',
    payment_method: 'card',
    status: 'completed',
    type: 'debit',
    ...overrides,
  };
}

// ─── computeKpis ─────────────────────────────────────────────────────────────

describe('computeKpis', () => {
  it('returns zeros for empty transactions', () => {
    const result = computeKpis([]);
    expect(result).toEqual({ totalIncome: 0, totalExpense: 0, netSavings: 0, savingRate: 0 });
  });

  it('sums income (positive amounts)', () => {
    const txns = [
      tx({ amount: 10000, transaction_date: '2026-03-01' }),
      tx({ amount: 5000, transaction_date: '2026-03-02' }),
    ];
    const result = computeKpis(txns);
    expect(result.totalIncome).toBe(15000);
    expect(result.totalExpense).toBe(0);
  });

  it('sums expenses (negative amounts) as absolute values', () => {
    const txns = [
      tx({ amount: -3000, transaction_date: '2026-03-01' }),
      tx({ amount: -2000, transaction_date: '2026-03-02' }),
    ];
    const result = computeKpis(txns);
    expect(result.totalIncome).toBe(0);
    expect(result.totalExpense).toBe(5000);
  });

  it('computes net savings as income minus expense', () => {
    const txns = [
      tx({ amount: 10000, transaction_date: '2026-03-01' }),
      tx({ amount: -4000, transaction_date: '2026-03-02' }),
    ];
    const result = computeKpis(txns);
    expect(result.netSavings).toBe(6000);
  });

  it('computes saving rate as percentage', () => {
    const txns = [
      tx({ amount: 10000, transaction_date: '2026-03-01' }),
      tx({ amount: -2500, transaction_date: '2026-03-02' }),
    ];
    const result = computeKpis(txns);
    expect(result.savingRate).toBeCloseTo(75, 1);
  });

  it('returns savingRate 0 when totalIncome is 0', () => {
    const txns = [tx({ amount: -500, transaction_date: '2026-03-01' })];
    const result = computeKpis(txns);
    expect(result.savingRate).toBe(0);
  });

  it('clamps negative saving rate to -100 (spend exceeds income)', () => {
    const txns = [
      tx({ amount: 100, transaction_date: '2026-03-01' }),
      tx({ amount: -50000, transaction_date: '2026-03-02' }),
    ];
    const result = computeKpis(txns);
    expect(result.savingRate).toBeGreaterThanOrEqual(-100);
  });

  it('skips zero-amount transactions', () => {
    const txns = [
      tx({ amount: 0, transaction_date: '2026-03-01' }),
      tx({ amount: 5000, transaction_date: '2026-03-02' }),
    ];
    const result = computeKpis(txns);
    expect(result.totalIncome).toBe(5000);
  });
});

// ─── mapSubscriptionToAxis ────────────────────────────────────────────────────

describe('mapSubscriptionToAxis', () => {
  it('maps Netflix to Entertainment', () => {
    expect(mapSubscriptionToAxis('Netflix Monthly Subscription')).toBe('Entertainment');
  });

  it('is case-insensitive', () => {
    expect(mapSubscriptionToAxis('SPOTIFY PREMIUM')).toBe('Entertainment');
  });

  it('maps broadband to Utilities', () => {
    expect(mapSubscriptionToAxis('Airtel Broadband Bill')).toBe('Utilities');
  });

  it('maps AWS to SaaS', () => {
    expect(mapSubscriptionToAxis('AWS Invoice')).toBe('SaaS');
  });

  it('maps Cult.fit to Fitness', () => {
    expect(mapSubscriptionToAxis('cult.fit membership')).toBe('Fitness');
  });

  it('maps Swiggy to Food Delivery', () => {
    expect(mapSubscriptionToAxis('SWIGGY ONE membership')).toBe('Food Delivery');
  });

  it('maps Uber to Transport', () => {
    expect(mapSubscriptionToAxis('Uber trip payment')).toBe('Transport');
  });

  it('returns null for unrecognised description', () => {
    expect(mapSubscriptionToAxis('Random grocery purchase')).toBeNull();
  });
});

// ─── buildRadarData ───────────────────────────────────────────────────────────

describe('buildRadarData', () => {
  it('returns all 6 axes with 0 for empty transactions', () => {
    const result = buildRadarData([]);
    expect(result).toHaveLength(6);
    expect(result.every(r => r.amount === 0)).toBe(true);
  });

  it('accumulates amounts per axis correctly', () => {
    const txns = [
      tx({ amount: -500, transaction_date: '2026-03-01', description: 'Netflix' }),
      tx({ amount: -200, transaction_date: '2026-03-02', description: 'Spotify' }),
      tx({ amount: -1500, transaction_date: '2026-03-03', description: 'AWS Invoice' }),
    ];
    const result = buildRadarData(txns);
    const entertainment = result.find(r => r.axis === 'Entertainment')!;
    const saas = result.find(r => r.axis === 'SaaS')!;
    expect(entertainment.amount).toBe(700);
    expect(saas.amount).toBe(1500);
  });

  it('ignores income (positive) transactions', () => {
    const txns = [
      tx({ amount: 5000, transaction_date: '2026-03-01', description: 'Netflix salary' }),
    ];
    const result = buildRadarData(txns);
    expect(result.every(r => r.amount === 0)).toBe(true);
  });
});

// ─── buildHeatmapGrid ─────────────────────────────────────────────────────────

describe('buildHeatmapGrid', () => {
  it('returns empty grid for empty transactions', () => {
    const result = buildHeatmapGrid([]);
    expect(result.cells).toHaveLength(0);
    expect(result.maxAmount).toBe(0);
    expect(result.weeks).toBe(0);
  });

  it('produces cells where dow=0 is always Monday', () => {
    // 2026-03-02 is a Monday
    const txns = [tx({ amount: -100, transaction_date: '2026-03-02' })];
    const result = buildHeatmapGrid(txns, 1);
    const cell = result.cells.find(c => c.date === '2026-03-02');
    expect(cell).toBeDefined();
    expect(cell!.dow).toBe(0); // Monday
  });

  it('tracks maxAmount correctly', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-03-01' }),
      tx({ amount: -500, transaction_date: '2026-03-02' }),
      tx({ amount: -300, transaction_date: '2026-03-03' }),
    ];
    const result = buildHeatmapGrid(txns);
    expect(result.maxAmount).toBe(500);
  });

  it('aggregates multiple transactions on the same day', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-03-01' }),
      tx({ amount: -200, transaction_date: '2026-03-01' }),
    ];
    const result = buildHeatmapGrid(txns);
    const cell = result.cells.find(c => c.date === '2026-03-01');
    expect(cell!.amount).toBe(300);
  });

  it('ignores income transactions', () => {
    const txns = [tx({ amount: 5000, transaction_date: '2026-03-01' })];
    const result = buildHeatmapGrid(txns);
    expect(result.cells).toHaveLength(0);
  });
});

// ─── computeDowAverages ───────────────────────────────────────────────────────

describe('computeDowAverages', () => {
  it('returns 7 entries in Mon–Sun order', () => {
    const result = computeDowAverages([]);
    expect(result).toHaveLength(7);
    expect(result[0].label).toBe('Mon');
    expect(result[6].label).toBe('Sun');
  });

  it('returns zero averages for empty transactions', () => {
    const result = computeDowAverages([]);
    expect(result.every(r => r.average === 0)).toBe(true);
    expect(result.every(r => !r.isPeak)).toBe(true);
  });

  it('computes correct average per day', () => {
    // 2026-03-02 is Monday — two transactions of 200 and 400 → avg 300
    const txns = [
      tx({ amount: -200, transaction_date: '2026-03-02' }),
      tx({ amount: -400, transaction_date: '2026-03-02' }),
    ];
    const result = computeDowAverages(txns);
    expect(result[0].label).toBe('Mon');
    expect(result[0].average).toBe(300);
  });

  it('marks the peak day as isPeak=true', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-03-02' }), // Mon
      tx({ amount: -900, transaction_date: '2026-03-07' }), // Sat
    ];
    const result = computeDowAverages(txns);
    const sat = result.find(r => r.label === 'Sat')!;
    expect(sat.isPeak).toBe(true);
  });

  it('ignores income transactions', () => {
    const txns = [tx({ amount: 5000, transaction_date: '2026-03-02' })];
    const result = computeDowAverages(txns);
    expect(result.every(r => r.average === 0)).toBe(true);
  });
});

// ─── buildCategoryTrendSeries ─────────────────────────────────────────────────

describe('buildCategoryTrendSeries', () => {
  it('returns empty for empty transactions', () => {
    const result = buildCategoryTrendSeries([]);
    expect(result.data).toHaveLength(0);
    expect(result.categories).toHaveLength(0);
  });

  it('produces one data point per distinct month', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-01-15', category: 'Food' }),
      tx({ amount: -200, transaction_date: '2026-02-10', category: 'Food' }),
    ];
    const result = buildCategoryTrendSeries(txns);
    expect(result.data).toHaveLength(2);
  });

  it('selects at most 5 categories', () => {
    const cats = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
    const txns = cats.map((cat, i) =>
      tx({ amount: -(i + 1) * 100, transaction_date: '2026-03-01', category: cat })
    );
    const result = buildCategoryTrendSeries(txns);
    expect(result.categories.length).toBeLessThanOrEqual(5);
  });

  it('fills 0 for categories with no spend in a given month', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-01-01', category: 'Food' }),
      tx({ amount: -200, transaction_date: '2026-02-01', category: 'Transport' }),
    ];
    const result = buildCategoryTrendSeries(txns);
    expect(result.categories).toContain('Food');
    expect(result.categories).toContain('Transport');
    const jan = result.data.find(d => d.month.startsWith('Jan'));
    expect(jan!['Transport']).toBe(0);
    const feb = result.data.find(d => d.month.startsWith('Feb'));
    expect(feb!['Food']).toBe(0);
  });

  it('ranks categories by total spend descending', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-03-01', category: 'Food' }),
      tx({ amount: -1000, transaction_date: '2026-03-02', category: 'Rent' }),
    ];
    const result = buildCategoryTrendSeries(txns);
    expect(result.categories[0]).toBe('Rent');
  });

  it('ignores income transactions', () => {
    const txns = [tx({ amount: 5000, transaction_date: '2026-03-01', category: 'Salary' })];
    const result = buildCategoryTrendSeries(txns);
    expect(result.data).toHaveLength(0);
  });
});

// ─── buildMonthlyBarData ──────────────────────────────────────────────────────

describe('buildMonthlyBarData', () => {
  it('returns empty for empty transactions', () => {
    expect(buildMonthlyBarData([])).toHaveLength(0);
  });

  it('produces one point per distinct month sorted chronologically', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-01-10' }),
      tx({ amount: -200, transaction_date: '2026-03-05' }),
      tx({ amount: -150, transaction_date: '2026-02-15' }),
    ];
    const result = buildMonthlyBarData(txns);
    expect(result).toHaveLength(3);
    expect(result[0].month).toMatch(/Jan/);
    expect(result[1].month).toMatch(/Feb/);
    expect(result[2].month).toMatch(/Mar/);
  });

  it('correctly sums income and expense per month', () => {
    const txns = [
      tx({ amount: 10000, transaction_date: '2026-03-01' }),
      tx({ amount: -3000, transaction_date: '2026-03-10' }),
      tx({ amount: -2000, transaction_date: '2026-03-20' }),
    ];
    const result = buildMonthlyBarData(txns);
    expect(result).toHaveLength(1);
    expect(result[0].income).toBe(10000);
    expect(result[0].expense).toBe(5000);
    expect(result[0].net).toBe(5000);
  });

  it('computes negative net when expense exceeds income', () => {
    const txns = [
      tx({ amount: 1000, transaction_date: '2026-03-01' }),
      tx({ amount: -5000, transaction_date: '2026-03-10' }),
    ];
    const result = buildMonthlyBarData(txns);
    expect(result[0].net).toBe(-4000);
  });

  it('caps to maxMonths most-recent months', () => {
    const txns = ['2025-01', '2025-02', '2025-03', '2025-04', '2025-05', '2025-06', '2025-07'].map(
      m => tx({ amount: -100, transaction_date: `${m}-01` })
    );
    const result = buildMonthlyBarData(txns, 3);
    expect(result).toHaveLength(3);
    expect(result[0].month).toMatch(/May/);
    expect(result[2].month).toMatch(/Jul/);
  });

  it('ignores transactions with invalid dates', () => {
    const txns = [
      tx({ amount: -100, transaction_date: 'invalid-date' }),
      tx({ amount: -200, transaction_date: '2026-03-01' }),
    ];
    const result = buildMonthlyBarData(txns);
    expect(result).toHaveLength(1);
  });
});

// ─── buildCategoryBreakdown ───────────────────────────────────────────────────

describe('buildCategoryBreakdown', () => {
  it('returns empty for empty transactions', () => {
    expect(buildCategoryBreakdown([])).toHaveLength(0);
  });

  it('returns empty when all transactions are income', () => {
    const txns = [tx({ amount: 5000, transaction_date: '2026-03-01', category: 'Salary' })];
    expect(buildCategoryBreakdown(txns)).toHaveLength(0);
  });

  it('ranks categories by total spend descending', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-03-01', category: 'Food' }),
      tx({ amount: -500, transaction_date: '2026-03-02', category: 'Rent' }),
      tx({ amount: -200, transaction_date: '2026-03-03', category: 'Transport' }),
    ];
    const result = buildCategoryBreakdown(txns);
    expect(result[0].category).toBe('Rent');
    expect(result[1].category).toBe('Transport');
    expect(result[2].category).toBe('Food');
  });

  it('computes percentage of total correctly', () => {
    const txns = [
      tx({ amount: -300, transaction_date: '2026-03-01', category: 'Food' }),
      tx({ amount: -700, transaction_date: '2026-03-02', category: 'Rent' }),
    ];
    const result = buildCategoryBreakdown(txns);
    expect(result[0].pct).toBeCloseTo(70, 1);
    expect(result[1].pct).toBeCloseTo(30, 1);
  });

  it('caps at maxCategories', () => {
    const txns = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'].map((cat, i) =>
      tx({ amount: -(i + 1) * 100, transaction_date: '2026-03-01', category: cat })
    );
    const result = buildCategoryBreakdown(txns, 5);
    expect(result).toHaveLength(5);
  });

  it('uses Uncategorized for transactions with no category', () => {
    const txns = [tx({ amount: -200, transaction_date: '2026-03-01', category: '' })];
    const result = buildCategoryBreakdown(txns);
    expect(result[0].category).toBe('Uncategorized');
  });
});

// ─── buildTopMerchants ────────────────────────────────────────────────────────

describe('buildTopMerchants', () => {
  it('returns empty for empty transactions', () => {
    expect(buildTopMerchants([])).toHaveLength(0);
  });

  it('ignores income (positive) transactions', () => {
    const txns = [tx({ amount: 5000, transaction_date: '2026-03-01', merchant_name: 'Salary Co' })];
    expect(buildTopMerchants(txns)).toHaveLength(0);
  });

  it('ranks merchants by total spend descending', () => {
    const txns = [
      tx({ amount: -100, transaction_date: '2026-03-01', merchant_name: 'Coffee Shop' }),
      tx({ amount: -500, transaction_date: '2026-03-02', merchant_name: 'Amazon' }),
      tx({ amount: -200, transaction_date: '2026-03-03', merchant_name: 'Swiggy' }),
    ];
    const result = buildTopMerchants(txns);
    expect(result[0].merchant).toBe('Amazon');
    expect(result[1].merchant).toBe('Swiggy');
    expect(result[2].merchant).toBe('Coffee Shop');
  });

  it('accumulates multiple transactions for the same merchant', () => {
    const txns = [
      tx({ amount: -200, transaction_date: '2026-03-01', merchant_name: 'Swiggy' }),
      tx({ amount: -300, transaction_date: '2026-03-02', merchant_name: 'Swiggy' }),
    ];
    const result = buildTopMerchants(txns);
    expect(result[0].amount).toBe(500);
    expect(result[0].count).toBe(2);
  });

  it('computes percentage of top-N total correctly', () => {
    const txns = [
      tx({ amount: -300, transaction_date: '2026-03-01', merchant_name: 'A' }),
      tx({ amount: -700, transaction_date: '2026-03-02', merchant_name: 'B' }),
    ];
    const result = buildTopMerchants(txns);
    expect(result[0].pct).toBeCloseTo(70, 1);
    expect(result[1].pct).toBeCloseTo(30, 1);
  });

  it('falls back to description when merchant_name is blank', () => {
    const txns = [
      tx({
        amount: -100,
        transaction_date: '2026-03-01',
        merchant_name: '',
        description: 'UPI Txn',
      }),
    ];
    const result = buildTopMerchants(txns);
    expect(result[0].merchant).toBe('UPI Txn');
  });

  it('caps at maxMerchants', () => {
    const txns = Array.from({ length: 10 }, (_, i) =>
      tx({ amount: -(i + 1) * 100, transaction_date: '2026-03-01', merchant_name: `M${i}` })
    );
    const result = buildTopMerchants(txns, 5);
    expect(result).toHaveLength(5);
  });
});
