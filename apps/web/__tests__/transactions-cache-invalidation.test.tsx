/**
 * Regression test for BUG-006: Transactions page shows stale categories after
 * background categorization, manual review save, or inline category edit.
 *
 * Root cause: all removeCachedData call sites use `transactions-cache:${userId}`
 * (no account ID) but the cache is written under `transactions-cache:${userId}:${accountId}`.
 * Every invalidation was a silent no-op — the wrong key was looked up.
 */
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
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
    getUncategorized: vi.fn(),
    getTransactionCounts: vi.fn(),
    updateTransaction: vi.fn(),
  },
  categorizationApi: {
    submitFeedback: vi.fn().mockResolvedValue({}),
  },
  ingestionApi: {
    importFile: vi.fn(),
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
    button: ({
      children,
      variants: _v,
      initial: _i,
      animate: _a,
      whileHover: _wh,
      whileTap: _wt,
      transition: _t,
      exit: _e,
      ...p
    }: React.ButtonHTMLAttributes<HTMLButtonElement> & Record<string, unknown>) => (
      <button {...p}>{children}</button>
    ),
    span: ({
      children,
      variants: _v,
      initial: _i,
      animate: _a,
      whileHover: _wh,
      whileTap: _wt,
      transition: _t,
      exit: _e,
      ...p
    }: React.HTMLAttributes<HTMLSpanElement> & Record<string, unknown>) => (
      <span {...p}>{children}</span>
    ),
  },
  AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// ----- Imports after mocks -----

import TransactionsPage from '../app/dashboard/transactions/page';
import { supabase } from '../lib/supabase/client';
import { accountsApi } from '../lib/api/client';
import { getCachedData, removeCachedData } from '../lib/utils/cache';
import { useAccount } from '../lib/contexts/AccountContext';

const MOCK_USER_ID = 'user-test-123';
const MOCK_ACCOUNT_UUID = 'account-uuid-only-account';

const MOCK_UNCATEGORIZED_TX = {
  id: 'tx-uncat-1',
  description: 'Amazon Purchase',
  amount: -500,
  category: 'Uncategorized',
  suggested_category: 'Shopping',
  confidence_score: 0.92,
  transaction_date: '2026-03-17',
  merchant_name: 'Amazon',
  payment_method: 'UPI',
  type: 'debit',
  currency: 'INR',
  created_at: '2026-03-17T00:00:00Z',
};

describe('Transactions cache invalidation key (BUG-006)', () => {
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
      data: { session: { access_token: 'fake-token', user: { id: MOCK_USER_ID } } },
      error: null,
    } as any);

    vi.mocked(accountsApi.getTransactions).mockResolvedValue({
      items: [],
      has_more: false,
      next_cursor: null,
    });

    vi.mocked(accountsApi.getTransactionCounts).mockResolvedValue({
      all: 1,
      debit: 1,
      credit: 0,
      uncategorized: 1,
    });

    vi.mocked(accountsApi.updateTransaction).mockResolvedValue({} as any);
  });

  it('re-fetches from API (not cache) after saveReviewCategory — categories reflect server state', async () => {
    /**
     * Scenario: uncategorized item has suggested_category. User clicks "Accept".
     * handleReviewSave calls removeCachedData then fetchTransactions.
     *
     * BEFORE fix (BUG-006):
     *   removeCachedData called with `transactions-cache:USER` (no account ID)
     *   → cache key `transactions-cache:USER:UUID` is NOT evicted
     *   → fetchTransactions hits cache again, serves stale data
     *   → test FAILS: removeCachedData not called with account-scoped key
     *
     * AFTER fix:
     *   removeCachedData called with `transactions-cache:USER:UUID`
     *   → cache evicted → fetchTransactions hits API → fresh data served
     *   → test PASSES
     */
    vi.mocked(accountsApi.getUncategorized).mockResolvedValue({
      items: [MOCK_UNCATEGORIZED_TX],
      count: 1,
    });

    render(<TransactionsPage />);

    // Wait for initial load to complete (loading spinner disappears)
    await waitFor(
      () => expect(screen.queryByText(/Loading transactions/i)).not.toBeInTheDocument(),
      { timeout: 5000 }
    );

    // Navigate to Review tab
    const reviewTab = screen.getByRole('button', { name: /review/i });
    fireEvent.click(reviewTab);

    // Wait for the uncategorized item's "Accept" button to appear
    await waitFor(
      () => expect(screen.getByRole('button', { name: /accept/i })).toBeInTheDocument(),
      { timeout: 3000 }
    );

    // Click Accept — triggers handleReviewSave which calls removeCachedData
    fireEvent.click(screen.getByRole('button', { name: /accept/i }));

    // Wait for updateTransaction to be called
    await waitFor(() => expect(accountsApi.updateTransaction).toHaveBeenCalled(), {
      timeout: 3000,
    });

    // CRITICAL: removeCachedData must be called with the account-scoped key
    // With bug: called as `transactions-cache:USER` — assertion fails
    // After fix: called as `transactions-cache:USER:UUID` — assertion passes
    expect(removeCachedData).toHaveBeenCalledWith(
      `transactions-cache:${MOCK_USER_ID}:${MOCK_ACCOUNT_UUID}`
    );
  });

  it('re-fetches from API (not cache) after saveEditedCategory — inline edit reflects server state', async () => {
    /**
     * Scenario: transaction row has edit (pencil) button. User opens it, picks
     * a category, saves. saveCategoryEdit calls removeCachedData then fetchTransactions.
     *
     * BEFORE fix (BUG-006):
     *   removeCachedData called with `transactions-cache:USER` (no account ID) → no-op
     *   → test FAILS
     *
     * AFTER fix:
     *   removeCachedData called with `transactions-cache:USER:UUID`
     *   → test PASSES
     */
    vi.mocked(accountsApi.getUncategorized).mockResolvedValue({ items: [], count: 0 });

    // Provide one transaction row so the edit pencil appears
    vi.mocked(accountsApi.getTransactions).mockResolvedValue({
      items: [
        {
          id: 'tx-editable-1',
          amount: -200,
          transaction_date: '2026-03-17',
          description: 'Zomato Order',
          category: 'Uncategorized',
          payment_method: 'UPI',
          merchant_name: 'Zomato',
          status: 'completed',
          type: 'debit',
          currency: 'INR',
          user_id: MOCK_USER_ID,
          created_at: '2026-03-17T00:00:00Z',
        },
      ],
      has_more: false,
      next_cursor: null,
    });

    render(<TransactionsPage />);

    // Wait for initial load
    await waitFor(
      () => expect(screen.queryByText(/Loading transactions/i)).not.toBeInTheDocument(),
      { timeout: 5000 }
    );

    // Wait for transaction row to appear
    await waitFor(() => expect(screen.getByText('Zomato')).toBeInTheDocument(), { timeout: 3000 });

    // Click the edit (pencil) button on the transaction row
    const editButton = screen.getByTitle('Edit category');
    fireEvent.click(editButton);

    // A category select should appear — pick any category
    await waitFor(() => expect(screen.getByRole('combobox')).toBeInTheDocument(), {
      timeout: 3000,
    });

    // Click the save (checkmark) button inside the inline editor
    const saveButton = screen.getByTitle('Save category');
    fireEvent.click(saveButton);

    // Wait for updateTransaction to be called
    await waitFor(() => expect(accountsApi.updateTransaction).toHaveBeenCalled(), {
      timeout: 3000,
    });

    // CRITICAL: removeCachedData must be called with the account-scoped key
    expect(removeCachedData).toHaveBeenCalledWith(
      `transactions-cache:${MOCK_USER_ID}:${MOCK_ACCOUNT_UUID}`
    );
  });
});
