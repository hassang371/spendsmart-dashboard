'use client';

import { AnimatePresence, motion } from 'framer-motion';
import { Building2, Check, ChevronDown, Link2 } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';

import { useAccount } from '@/lib/contexts/AccountContext';
import { SyncStatusIndicator } from './SyncStatusIndicator';

/**
 * Sidebar dropdown for selecting the active bank account.
 * Placed below navigation, above the profile section.
 */
export function AccountSwitcher() {
  const { accounts, activeAccountId, setActiveAccountId, loading } = useAccount();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const activeLabel =
    activeAccountId === 'all'
      ? 'All Accounts'
      : accounts.find((a) => a.id === activeAccountId)?.account_name ?? 'All Accounts';

  return (
    <div ref={ref} className="relative px-2 mb-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
      >
        <Building2 size={16} className="shrink-0 text-primary" />
        <span className="flex-1 truncate text-left text-xs">{loading ? 'Loading…' : activeLabel}</span>
        <ChevronDown
          size={14}
          className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.97, y: -4 }}
            className="absolute bottom-full mb-2 left-0 right-0 rounded-2xl bg-popover border border-border shadow-xl z-50 overflow-hidden p-1"
          >
            {/* All Accounts option */}
            <button
              onClick={() => { setActiveAccountId('all'); setOpen(false); }}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-sm transition-colors ${
                activeAccountId === 'all'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
              }`}
            >
              <span className="font-medium">All Accounts</span>
              {activeAccountId === 'all' && <Check size={14} className="text-primary" />}
            </button>

            {/* Per-account options */}
            {accounts.map((account) => (
              <button
                key={account.id}
                onClick={() => { setActiveAccountId(account.id); setOpen(false); }}
                className={`w-full flex items-center gap-2 px-3 py-2 rounded-xl text-sm transition-colors ${
                  activeAccountId === account.id
                    ? 'bg-muted text-foreground'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
                }`}
              >
                <div className="flex-1 min-w-0 text-left">
                  <p className="truncate font-medium text-xs">{account.account_name}</p>
                  {account.masked_number && (
                    <p className="text-[10px] text-muted-foreground">••{account.masked_number}</p>
                  )}
                </div>
                <SyncStatusIndicator status={account.sync_status} />
                {activeAccountId === account.id && (
                  <Check size={14} className="text-primary shrink-0" />
                )}
              </button>
            ))}

            {accounts.length === 0 && !loading && (
              <p className="px-3 py-2 text-xs text-muted-foreground">No linked accounts</p>
            )}

            {/* Link a new account */}
            <div className="border-t border-border mt-1 pt-1">
              <Link
                href="/dashboard/accounts"
                onClick={() => setOpen(false)}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-primary hover:bg-primary/10 transition-colors"
              >
                <Link2 size={14} />
                Manage Accounts
              </Link>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
