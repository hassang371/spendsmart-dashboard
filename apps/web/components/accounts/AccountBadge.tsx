'use client';

import { useRef, useState, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';
import { useAccount } from '@/lib/contexts/AccountContext';

interface AccountBadgeProps {
  onClick?: () => void;
}

/**
 * Small chip displayed at the top of content pages showing which account
 * is currently active. Clicking opens a self-contained inline dropdown to
 * switch accounts without requiring any wiring from the caller.
 */
export function AccountBadge({ onClick }: AccountBadgeProps) {
  const { activeAccountId, activeAccount, accounts, setActiveAccountId } = useAccount();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const label =
    activeAccountId === 'all'
      ? 'All Accounts'
      : activeAccount?.account_name ?? activeAccountId;

  // Close dropdown when clicking outside
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  function handleToggle() {
    if (onClick) {
      onClick();
    } else {
      setOpen((v) => !v);
    }
  }

  function handleSelect(id: string) {
    setActiveAccountId(id);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={handleToggle}
        className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-3 py-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/50 transition-colors"
      >
        <span className="h-1.5 w-1.5 rounded-full bg-primary" />
        {label}
        <ChevronDown size={12} className={open ? 'rotate-180 transition-transform' : 'transition-transform'} />
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-1 z-50 min-w-[160px] rounded-xl border border-border bg-card shadow-lg py-1">
          <button
            onClick={() => handleSelect('all')}
            className={`w-full text-left px-3 py-1.5 text-xs hover:bg-muted/60 transition-colors flex items-center gap-2 ${activeAccountId === 'all' ? 'font-bold text-primary' : 'text-foreground'}`}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-primary/40 shrink-0" />
            All Accounts
          </button>
          {accounts.map((acct) => (
            <button
              key={acct.id}
              onClick={() => handleSelect(acct.id)}
              className={`w-full text-left px-3 py-1.5 text-xs hover:bg-muted/60 transition-colors flex items-center gap-2 ${activeAccountId === acct.id ? 'font-bold text-primary' : 'text-foreground'}`}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-primary/40 shrink-0" />
              {acct.account_name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
