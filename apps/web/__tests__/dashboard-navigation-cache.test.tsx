/**
 * Regression test for BUG-005: Overview page shows "Welcome to SCALE" empty state
 * on client-side navigation even when the user has transactions in the database.
 *
 * Root cause (Defect 4): the anyCheck existence query incorrectly filters by
 * account_id, so when the active account has no transactions the global existence
 * check also returns empty, setting hasTransactionsEver=false.
 */
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { vi, describe, it, expect, beforeEach } from 'vitest';

// ----- Module mocks (hoisted by vitest) -----

vi.mock('../lib/supabase/client', () => ({
  supabase: {
    auth: {
      getUser: vi.fn(),
      getSession: vi.fn(),
    },
  },
}));

vi.mock('../lib/api/client', () => ({
  accountsApi: {
    getTransactions: vi.fn(),
  },
}));

vi.mock('../lib/utils/cache', () => ({
  getCachedData: vi.fn().mockReturnValue(null),
  setCachedData: vi.fn(),
  removeCachedData: vi.fn(),
}));

vi.mock('../lib/contexts/AccountContext', () => ({
  useAccount: vi.fn(),
}));

vi.mock('../components/accounts/AccountBadge', () => ({
  AccountBadge: () => null,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Cell: () => null,
  XAxis: () => null,
  Tooltip: () => null,
  PieChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Pie: () => null,
}));

vi.mock('framer-motion', () => ({
  motion: {
    div: ({
      children,
      variants: _v,
      initial: _i,
      animate: _a,
      whileHover: _wh,
      whileTap: _wt,
      transition: _t,
      exit: _e,
      ...p
    }: React.HTMLAttributes<HTMLDivElement> & Record<string, unknown>) => (
      <div {...p}>{children}</div>
    ),
    section: ({
      children,
      variants: _v,
      initial: _i,
      animate: _a,
      whileHover: _wh,
      whileTap: _wt,
      transition: _t,
      exit: _e,
      ...p
    }: React.HTMLAttributes<HTMLElement> & Record<string, unknown>) => (
      <section {...p}>{children}</section>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ----- Imports after mocks -----

import OverviewPage from '../app/dashboard/page';
import { supabase } from '../lib/supabase/client';
import { accountsApi } from '../lib/api/client';
import { getCachedData } from '../lib/utils/cache';
import { useAccount } from '../lib/contexts/AccountContext';

const MOCK_USER_ID = 'user-test-123';
const MOCK_ACCOUNT_UUID = 'account-uuid-only-account';

// A transaction with an old date so it falls outside the current weekly/monthly
// period — keeps periodExpenses empty while hasTransactionsEver can still be true.
const TRANSACTION_ON_DIFFERENT_ACCOUNT = {
  id: 'tx-global-1',
  amount: -500,
  transaction_date: '2020-01-15',
  description: 'Old Transaction',
  category: 'Food',
  payment_method: 'UPI',
  merchant_name: 'Test Merchant',
  status: 'completed',
  type: 'debit',
  currency: 'INR',
  user_id: MOCK_USER_ID,
  created_at: '2020-01-15T00:00:00Z',
};

describe('Overview page — empty state on client-side navigation back (BUG-005)', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(useAccount).mockReturnValue({
      activeAccountId: MOCK_ACCOUNT_UUID,
      setActiveAccountId: vi.fn(),
      accounts: [],
      activeAccount: null,
      loading: false,
      refreshAccounts: vi.fn(),
    });

    vi.mocked(getCachedData).mockReturnValue(null);

    vi.mocked(supabase.auth.getUser).mockResolvedValue({
      data: {
        user: {
          id: MOCK_USER_ID,
          email: 'test@example.com',
          user_metadata: { full_name: 'Test User' },
          aud: 'authenticated',
          created_at: '',
          app_metadata: {},
          role: 'authenticated',
          updated_at: '',
        },
      },
      error: null,
    } as ReturnType<typeof supabase.auth.getUser> extends Promise<infer R> ? R : never);

    vi.mocked(supabase.auth.getSession).mockResolvedValue({
      data: { session: { access_token: 'fake-token' } },
      error: null,
    } as any);
  });

  it('does not show Welcome empty state after navigating back to overview when UUID cache was previously empty but global transactions exist', async () => {
    /**
     * Scenario: the user has transactions in the DB but they are NOT associated with
     * the currently-selected account UUID (e.g. imported before account linking, or
     * the account was re-linked and got a new UUID).
     *
     * BEFORE fix (Defect 4):
     *   anyCheck passes `account_id: MOCK_ACCOUNT_UUID` → mock returns []
     *   → hasTransactionsEver = false → "Welcome to SCALE" shown → test FAILS
     *
     * AFTER fix (Defect 4):
     *   anyCheck omits account_id → mock returns [TRANSACTION_ON_DIFFERENT_ACCOUNT]
     *   → hasTransactionsEver = true → "Welcome to SCALE" NOT shown → test PASSES
     */
    vi.mocked(accountsApi.getTransactions).mockImplementation((_token, params) => {
      if (params?.account_id === MOCK_ACCOUNT_UUID) {
        // Account-scoped call: no transactions for this UUID
        return Promise.resolve({ items: [], has_more: false, next_cursor: null });
      }
      // Global call (anyCheck after fix — called without account_id)
      return Promise.resolve({
        items: [TRANSACTION_ON_DIFFERENT_ACCOUNT],
        has_more: false,
        next_cursor: null,
      });
    });

    render(<OverviewPage />);

    // The h1 greeting ("Hi, Test") only renders when loading=false — wait for it
    await waitFor(() => expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument(), {
      timeout: 5000,
    });

    // Must NOT show "Welcome to SCALE! Add first transaction"
    // (user has transactions globally, just not for this specific account in this period)
    expect(screen.queryByText(/Welcome to SCALE/i)).not.toBeInTheDocument();
  });
});
