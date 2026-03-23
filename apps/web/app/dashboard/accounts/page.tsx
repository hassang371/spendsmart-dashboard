'use client';

import { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Building2,
  Check,
  ChevronRight,
  ExternalLink,
  FileUp,
  Loader2,
  RefreshCw,
  Unlink,
  X,
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import { supabase } from '../../../lib/supabase/client';
import { type BankAccount, bankAccountsApi } from '../../../lib/api/client';
import { SyncStatusIndicator } from '@/components/accounts/SyncStatusIndicator';

// ── helpers ────────────────────────────────────────────────────────────────

function consentBadgeClass(status: BankAccount['consent_status']): string {
  switch (status) {
    case 'active':
      return 'bg-green-500/15 text-green-400 border-green-500/30';
    case 'pending':
      return 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30';
    case 'expired':
    case 'revoked':
      return 'bg-red-500/15 text-red-400 border-red-500/30';
    default:
      return 'bg-muted text-muted-foreground border-border';
  }
}

// ── main page ──────────────────────────────────────────────────────────────

export default function AccountsPage() {
  const router = useRouter();
  const [token, setToken] = useState('');
  const [accounts, setAccounts] = useState<BankAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [linking, setLinking] = useState(false);
  const [showVuaPrompt, setShowVuaPrompt] = useState(false);
  const [mobileNumber, setMobileNumber] = useState('');
  const [syncing, setSyncing] = useState<string | null>(null);
  const [unlinking, setUnlinking] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const selectedAccount = accounts.find(a => a.id === selectedId) ?? null;

  // Auth + initial fetch
  useEffect(() => {
    (async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.access_token) {
        router.replace('/login');
        return;
      }
      setToken(session.access_token);
      await fetchAccounts(session.access_token);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function fetchAccounts(t: string = token) {
    try {
      setLoading(true);
      const data = await bankAccountsApi.list(t);
      setAccounts(data);
      if (!selectedId && data.length > 0) {
        setSelectedId(data[0].id);
      }
    } catch {
      setError('Failed to load accounts.');
    } finally {
      setLoading(false);
    }
  }

  function initiateLinkPrompt() {
    setError(null);
    setShowVuaPrompt(true);
  }

  async function handleLink(e: React.FormEvent) {
    e.preventDefault();
    if (!mobileNumber || mobileNumber.length < 10) {
      setError('Please enter a valid 10-digit mobile number.');
      return;
    }

    setLinking(true);
    setShowVuaPrompt(false);
    setError(null);
    try {
      // For sandbox/OneMoney, the VUA format is exactly `<number>@onemoney`
      const vua = `${mobileNumber}@onemoney`;
      const res = await bankAccountsApi.link(token, { vua, fi_types: ['DEPOSIT'] });
      // Redirect user to Setu consent page
      window.location.href = res.redirect_url;
    } catch {
      setError('Could not initiate account linking. Please try again.');
      setLinking(false);
    }
  }

  async function handleSync(accountId: string) {
    setSyncing(accountId);
    setError(null);
    try {
      await bankAccountsApi.sync(accountId, token);
      await fetchAccounts();
    } catch {
      setError('Sync failed. Please try again.');
    } finally {
      setSyncing(null);
    }
  }

  async function handleUnlink(accountId: string) {
    setUnlinking(accountId);
    setError(null);
    try {
      await bankAccountsApi.unlink(accountId, token);
      setSelectedId(null);
      await fetchAccounts();
    } catch {
      setError('Could not unlink account.');
    } finally {
      setUnlinking(null);
    }
  }

  return (
    <div className="h-full flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Accounts</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Manage your linked bank accounts and file imports.
          </p>
        </div>
        <button
          onClick={initiateLinkPrompt}
          disabled={linking}
          className="flex items-center gap-2 rounded-2xl bg-primary px-4 py-2.5 text-sm font-bold text-primary-foreground hover:opacity-90 disabled:opacity-50 transition-opacity shadow-lg shadow-primary/20"
        >
          {linking ? <Loader2 size={16} className="animate-spin" /> : <ExternalLink size={16} />}
          Link Account
        </button>
      </div>

      {showVuaPrompt && (
        <div className="rounded-xl border border-border bg-card p-4 flex flex-col gap-3">
          <p className="text-sm font-medium">Link a new bank account</p>
          <p className="text-xs text-muted-foreground">
            Please enter your mobile number registered with your bank. You will receive an OTP from
            our Account Aggregator partner (OneMoney).
          </p>
          <form onSubmit={handleLink} className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground pl-2">+91</span>
            <input
              type="text"
              autoFocus
              placeholder="9876543210"
              value={mobileNumber}
              onChange={e => setMobileNumber(e.target.value.replace(/\D/g, '').slice(0, 10))}
              className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
              required
            />
            <button
              type="submit"
              disabled={linking || mobileNumber.length !== 10}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-50"
            >
              Continue
            </button>
            <button
              type="button"
              onClick={() => setShowVuaPrompt(false)}
              className="rounded-lg border border-border px-4 py-2 text-sm font-semibold hover:bg-muted"
            >
              Cancel
            </button>
          </form>
        </div>
      )}

      {error && (
        <div className="flex items-center gap-2 rounded-xl bg-destructive/10 border border-destructive/30 px-4 py-2.5 text-sm text-destructive">
          <X size={14} className="shrink-0" />
          {error}
          <button onClick={() => setError(null)} className="ml-auto">
            <X size={14} />
          </button>
        </div>
      )}

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left: Account List */}
        <div className="w-72 shrink-0 flex flex-col gap-2 overflow-y-auto">
          {loading ? (
            <div className="flex-1 flex items-center justify-center">
              <Loader2 size={20} className="animate-spin text-muted-foreground" />
            </div>
          ) : accounts.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center p-6">
              <Building2 size={32} className="text-muted-foreground/40" />
              <p className="text-sm text-muted-foreground">No accounts linked yet.</p>
            </div>
          ) : (
            accounts.map(account => (
              <button
                key={account.id}
                onClick={() => setSelectedId(account.id)}
                className={`w-full flex items-center gap-3 rounded-2xl border p-3 text-left transition-all duration-200 ${
                  selectedId === account.id
                    ? 'border-primary/60 bg-primary/5 shadow-md shadow-primary/10'
                    : 'border-border bg-card hover:border-border/80 hover:bg-muted/40'
                } ${account.is_manual ? 'border-yellow-500/30' : ''}`}
              >
                <div
                  className={`h-10 w-10 shrink-0 flex items-center justify-center rounded-xl ${
                    account.is_manual
                      ? 'bg-yellow-500/15 text-yellow-400'
                      : 'bg-primary/10 text-primary'
                  }`}
                >
                  {account.is_manual ? <FileUp size={18} /> : <Building2 size={18} />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm font-semibold">{account.account_name}</p>
                  {account.masked_number && (
                    <p className="text-xs text-muted-foreground">••{account.masked_number}</p>
                  )}
                  <SyncStatusIndicator status={account.sync_status} className="mt-0.5" />
                </div>
                {selectedId === account.id && (
                  <ChevronRight size={14} className="text-primary shrink-0" />
                )}
              </button>
            ))
          )}
        </div>

        {/* Right: Detail Panel */}
        <div className="flex-1 min-w-0">
          <AnimatePresence mode="wait">
            {selectedAccount ? (
              <motion.div
                key={selectedAccount.id}
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                className="h-full rounded-[2rem] border border-border bg-card p-6 flex flex-col gap-6"
              >
                {/* Account header */}
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-bold">{selectedAccount.account_name}</h2>
                    <div className="flex items-center gap-2 mt-1 flex-wrap">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium ${consentBadgeClass(selectedAccount.consent_status)}`}
                      >
                        {selectedAccount.consent_status}
                      </span>
                      {selectedAccount.institution && (
                        <span className="text-xs text-muted-foreground">
                          {selectedAccount.institution}
                        </span>
                      )}
                      {selectedAccount.masked_number && (
                        <span className="text-xs text-muted-foreground">
                          ••{selectedAccount.masked_number}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {/* Sync button — not shown for manual accounts */}
                    {!selectedAccount.is_manual && selectedAccount.consent_status === 'active' && (
                      <button
                        onClick={() => handleSync(selectedAccount.id)}
                        disabled={syncing === selectedAccount.id}
                        className="flex items-center gap-1.5 rounded-xl border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted transition-colors disabled:opacity-50"
                      >
                        {syncing === selectedAccount.id ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <RefreshCw size={14} />
                        )}
                        Sync
                      </button>
                    )}

                    {/* Unlink — not shown for manual account */}
                    {!selectedAccount.is_manual && (
                      <button
                        onClick={() => handleUnlink(selectedAccount.id)}
                        disabled={unlinking === selectedAccount.id}
                        className="flex items-center gap-1.5 rounded-xl border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs font-medium text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-50"
                      >
                        {unlinking === selectedAccount.id ? (
                          <Loader2 size={14} className="animate-spin" />
                        ) : (
                          <Unlink size={14} />
                        )}
                        Unlink
                      </button>
                    )}
                  </div>
                </div>

                {/* Account metadata */}
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {[
                    { label: 'Account Type', value: selectedAccount.account_type },
                    { label: 'Currency', value: selectedAccount.currency },
                    { label: 'Provider', value: selectedAccount.provider ?? 'Manual' },
                    {
                      label: 'Last Synced',
                      value: selectedAccount.last_synced_at
                        ? new Date(selectedAccount.last_synced_at).toLocaleString()
                        : 'Never',
                    },
                    {
                      label: 'Sync Status',
                      value: <SyncStatusIndicator status={selectedAccount.sync_status} />,
                    },
                    {
                      label: 'Linked',
                      value: new Date(selectedAccount.created_at).toLocaleDateString(),
                    },
                  ].map(({ label, value }) => (
                    <div key={label} className="rounded-xl bg-muted/40 p-3">
                      <p className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide">
                        {label}
                      </p>
                      <div className="mt-1 text-sm font-medium">{value}</div>
                    </div>
                  ))}
                </div>

                {/* Trust signals for active AA accounts */}
                {!selectedAccount.is_manual && selectedAccount.consent_status === 'active' && (
                  <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-4 text-sm text-green-400">
                    <div className="flex items-center gap-2 font-semibold mb-2">
                      <Check size={14} />
                      Read-only access
                    </div>
                    <ul className="space-y-1 text-xs text-green-400/80">
                      <li>• Your credentials are never stored by SCALE.</li>
                      <li>• Access can be revoked at any time.</li>
                      <li>• Regulated by RBI Account Aggregator framework.</li>
                    </ul>
                  </div>
                )}

                {/* Manual import hint */}
                {selectedAccount.is_manual && (
                  <div className="rounded-xl border border-yellow-500/20 bg-yellow-500/5 p-4 text-sm text-yellow-400">
                    <p className="font-semibold mb-1">Manual Import Account</p>
                    <p className="text-xs text-yellow-400/80">
                      Transactions imported from CSV / PDF files are stored here. Go to the
                      Transactions page to import a file.
                    </p>
                  </div>
                )}
              </motion.div>
            ) : (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="h-full flex flex-col items-center justify-center gap-4 rounded-[2rem] border border-dashed border-border text-center p-8"
              >
                <Building2 size={40} className="text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">Select an account to see details.</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
