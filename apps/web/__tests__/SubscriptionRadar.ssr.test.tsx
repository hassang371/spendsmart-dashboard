// @vitest-environment node
/**
 * SSR safety test for SubscriptionRadar.
 * Must run in Node environment (not jsdom) so that `window` is genuinely absent.
 * If the component accesses `window` at render time, this test will throw
 * "ReferenceError: window is not defined" — which is exactly the bug being caught.
 *
 * Refs: docs/bugs/BUG-010-subscriptionradar-window-ssr-crash.md
 */
import { it, expect, vi } from 'vitest';
import { renderToString } from 'react-dom/server';
import { createElement } from 'react';

// Mock framer-motion to avoid SSR issues unrelated to the window.innerWidth bug
vi.mock('framer-motion', () => ({
  motion: new Proxy(
    {},
    {
      get: (_target, prop) => {
        const tag = String(prop);
        return ({ children, ...rest }: Record<string, unknown>) =>
          createElement(tag === 'div' ? 'div' : 'div', rest, children as React.ReactNode);
      },
    }
  ),
}));

// Mock recharts to avoid ResizeObserver (browser API) in Node
vi.mock('recharts', () => ({
  PieChart: ({ children }: { children?: React.ReactNode }) => createElement('div', null, children),
  Pie: () => createElement('div', null),
  Cell: () => createElement('div', null),
  ResponsiveContainer: ({ children }: { children?: React.ReactNode }) =>
    createElement('div', null, children),
  Tooltip: () => createElement('div', null),
}));

import { SubscriptionRadar } from '../app/dashboard/analytics/components/SubscriptionRadar';
import type { Transaction } from '../lib/api/client';

// Non-empty transactions are required: SubscriptionRadar returns early for `length === 0`,
// bypassing the window.innerWidth access. The test must reach the compact view render.
const mockTransactions: Transaction[] = [
  {
    id: 'tx-1',
    user_id: 'user-1',
    transaction_date: '2026-03-01',
    amount: -500,
    currency: 'INR',
    description: 'Netflix',
    merchant_name: 'Netflix',
    category: 'Entertainment',
    payment_method: 'card',
    status: 'completed',
    type: 'debit',
  },
];

it('renders without accessing window during SSR', () => {
  expect(() => {
    renderToString(createElement(SubscriptionRadar, { transactions: mockTransactions }));
  }).not.toThrow();
});
