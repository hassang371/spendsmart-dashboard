'use client';

/**
 * AccountContext — tracks which bank account is "active" across the dashboard.
 *
 * - activeAccountId: UUID of the selected account, or 'all' for aggregate view.
 * - Persists via localStorage / sessionStorage through getAppStorage().
 * - Provides accounts list fetched once at mount so child components don't
 *   each need to fetch independently.
 */

import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { type BankAccount, bankAccountsApi } from '@/lib/api/client';
import { getAppStorage } from '@/lib/utils/storage';

const STORAGE_KEY = 'scale_active_account_id';

interface AccountContextValue {
  /** UUID of active account, or 'all' for aggregate view. */
  activeAccountId: string;
  setActiveAccountId: (id: string) => void;
  accounts: BankAccount[];
  /** Active BankAccount object, or null when 'all' is selected. */
  activeAccount: BankAccount | null;
  /** True while the initial accounts list is loading. */
  loading: boolean;
  /** Refetch accounts list (e.g. after linking a new account). */
  refreshAccounts: () => Promise<void>;
}

const AccountContext = createContext<AccountContextValue | null>(null);

export function AccountProvider({ children, token }: { children: React.ReactNode; token: string }) {
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [loading, setLoading] = useState(true);
  // Lazy initializer reads storage synchronously on first render, eliminating
  // the 'all'→UUID state transition that caused concurrent overview fetches.
  const [activeAccountId, setActiveAccountIdState] = useState<string>(() => {
    const storage = getAppStorage();
    return storage?.getItem(STORAGE_KEY) || 'all';
  });

  const fetchAccounts = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    try {
      const data = await bankAccountsApi.list(token);
      setAccounts(data);

      // Auto-select first account if no persisted preference exists.
      // 'all' is only the initial fallback — never the desired default.
      const storage = getAppStorage();
      const persisted = storage?.getItem(STORAGE_KEY);
      // Auto-select first account when no real preference is stored.
      // Treat stored 'all' as "no preference" — 'all' is never a useful default.
      if ((!persisted || persisted === 'all') && data.length > 0) {
        const firstId = data[0].id;
        setActiveAccountIdState(firstId);
        storage?.setItem(STORAGE_KEY, firstId);
      }
    } catch {
      // Accounts unavailable — degrade gracefully, context still usable
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  const setActiveAccountId = useCallback((id: string) => {
    setActiveAccountIdState(id);
    const storage = getAppStorage();
    storage?.setItem(STORAGE_KEY, id);
  }, []);

  const activeAccount = accounts.find(a => a.id === activeAccountId) ?? null;

  return (
    <AccountContext.Provider
      value={{
        activeAccountId,
        setActiveAccountId,
        accounts,
        activeAccount,
        loading,
        refreshAccounts: fetchAccounts,
      }}
    >
      {children}
    </AccountContext.Provider>
  );
}

export function useAccount(): AccountContextValue {
  const ctx = useContext(AccountContext);
  if (!ctx) {
    throw new Error('useAccount must be used within an AccountProvider');
  }
  return ctx;
}
