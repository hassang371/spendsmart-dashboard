'use client';

import { ChevronDown } from 'lucide-react';
import { useAccount } from '@/lib/contexts/AccountContext';

interface AccountBadgeProps {
  onClick?: () => void;
}

/**
 * Small chip displayed at the top of content pages showing which account
 * is currently active. Clicking opens the AccountSwitcher (caller's job).
 */
export function AccountBadge({ onClick }: AccountBadgeProps) {
  const { activeAccountId, activeAccount } = useAccount();

  const label =
    activeAccountId === 'all'
      ? 'All Accounts'
      : activeAccount?.account_name ?? activeAccountId;

  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
    >
      <span className="h-1.5 w-1.5 rounded-full bg-primary" />
      {label}
      <ChevronDown size={12} />
    </button>
  );
}
