'use client';

import { useEffect, useState, useMemo, Suspense } from 'react';
import { useRouter, useSearchParams, usePathname } from 'next/navigation';
import { motion, type Variants } from 'framer-motion';
import { Loader2, Activity, ChevronDown } from 'lucide-react';
import { supabase } from '../../../lib/supabase/client';
import { accountsApi, type Transaction } from '../../../lib/api/client';

import { MonthlyComparison } from './components/MonthlyComparison';
import { SubscriptionRadar } from './components/SubscriptionRadar';
import { CategoryDistribution } from './components/CategoryDistribution';
import { MerchantLeaderboard } from './components/MerchantLeaderboard';
import { AnalyticsEmptyState } from './components/AnalyticsEmptyState';
import { ExpandableCard } from '../../../components/ui/ExpandableCard';
import { getCachedData, setCachedData } from '../../../lib/utils/cache';

const ANALYTICS_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour cache

export function monthName(index: number): string {
  return [
    'January',
    'February',
    'March',
    'April',
    'May',
    'June',
    'July',
    'August',
    'September',
    'October',
    'November',
    'December',
  ][index];
}

function AnalyticsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const pathname = usePathname();

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const hasParams = searchParams.toString().length > 0;
  const yearParam = hasParams ? (searchParams.get('year') || 'all') : 'all';
  const monthParam = hasParams ? (searchParams.get('month') || 'all') : 'all';
  const relativeParam = hasParams ? (searchParams.get('relative') || 'none') : 'this_month';

  const updateFilter = (type: 'year' | 'month' | 'relative', value: string) => {
    const params = new URLSearchParams(searchParams);
    if (!hasParams && type !== 'relative') {
      params.set('relative', 'none');
    }
    if (type === 'relative' && value !== 'none') {
      // If setting a quick range, clear explicit year/month
      params.set('year', 'all');
      params.set('month', 'all');
    } else if (type === 'year' || type === 'month') {
      // Always clear relative range when explicitly setting/clearing year or month
      params.set('relative', 'none');
      if (type === 'year' && value === 'all') {
        params.set('month', 'all');
      }
    }
    params.set(type, value);
    router.replace(`${pathname}?${params.toString()}`);
  };

  useEffect(() => {
    let mounted = true;

    const fetchData = async () => {
      try {
        const {
          data: { user },
          error: userError,
        } = await supabase.auth.getUser();
        if (userError || !user) {
          router.replace('/login');
          return;
        }

        const cacheKey = `analytics-cache-v2:${user.id}`;
        const cachedData = getCachedData<{
          items: Transaction[];
          truncated?: boolean;
          totalCount?: number | null;
        }>(cacheKey, ANALYTICS_CACHE_TTL_MS);

        if (cachedData) {
          if (mounted) {
            setTransactions(cachedData.items);
            setLoading(false);
          }
          return;
        }

        // Get auth token for API call
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (!session?.access_token) {
          router.replace('/login');
          return;
        }

        // Single request: up to 500 transactions to ensure accurate analytics within safe backend limits.
        const response = await accountsApi.getTransactions(session.access_token, {
          limit: 500,
          include_total: true,
        });

        if (!mounted) return;

        setTransactions(response.items);

        setCachedData(cacheKey, {
          items: response.items,
        });
      } catch (err: unknown) {
        if (!mounted) return;
        console.error("Analytics fetch error:", err);
        let message = 'Failed to load analytics data.';
        if (err instanceof Error) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          message = err.message === '[object Object]' && (err as any).data
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            ? JSON.stringify((err as any).data.detail || (err as any).data)
            : err.message;
        }
        setError(message);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    fetchData();
    return () => {
      mounted = false;
    };
  }, [router]);

  // Animation Variants
  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1 },
    },
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { type: 'spring', stiffness: 300, damping: 24 },
    },
  };

  // Dynamic list of years present in the transactions
  const years = useMemo(() => {
    const values = new Set<string>();
    for (const tx of transactions) {
      const d = new Date(tx.transaction_date);
      if (!Number.isNaN(d.getTime())) values.add(String(d.getFullYear()));
    }
    return ['all', ...Array.from(values).sort((a, b) => Number(b) - Number(a))];
  }, [transactions]);

  // Client-side filtering for seamless UX
  const filteredTransactions = useMemo(() => {
    if (!transactions.length) return [];

    // Sort transactions by date descending to ensure charts look correct
    const sorted = [...transactions].sort((a, b) => new Date(b.transaction_date).getTime() - new Date(a.transaction_date).getTime());

    return sorted.filter(t => {
      const date = new Date(t.transaction_date);
      if (Number.isNaN(date.getTime())) return false;

      if (yearParam !== 'all' && String(date.getFullYear()) !== yearParam) return false;
      if (
        yearParam !== 'all' &&
        monthParam !== 'all' &&
        String(date.getMonth()) !== monthParam
      )
        return false;

      if (relativeParam !== 'none') {
        const now = new Date();
        const start = new Date();
        start.setHours(0, 0, 0, 0);

        if (relativeParam === 'this_week') {
          const day = start.getDay() || 7;
          start.setDate(start.getDate() - (day - 1));
          if (date < start || date > now) return false;
        } else if (relativeParam === 'this_month') {
          start.setDate(1);
          if (date < start || date > now) return false;
        } else if (relativeParam === 'last_30') {
          start.setDate(now.getDate() - 30);
          if (date < start || date > now) return false;
        } else if (relativeParam === 'last_90') {
          start.setDate(now.getDate() - 90);
          if (date < start || date > now) return false;
        } else if (relativeParam === 'last_180') {
          start.setDate(now.getDate() - 180);
          if (date < start || date > now) return false;
        }
      }

      return true;
    });
  }, [transactions, yearParam, monthParam, relativeParam]);

  if (loading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="rounded-2xl border border-destructive/20 bg-destructive/10 p-6 text-destructive-foreground backdrop-blur-md">
          <Activity className="mx-auto mb-2 h-8 w-8 text-destructive" />
          <p>{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 rounded-lg bg-destructive/20 px-4 py-2 hover:bg-destructive/30"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty State Check
  if (transactions.length === 0) {
    return <AnalyticsEmptyState />;
  }



  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-4 md:p-8"
    >
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <motion.div variants={itemVariants} className="flex flex-col gap-1">
          <h1 className="text-4xl font-black text-foreground tracking-tight">Analytics</h1>
          <p className="text-sm font-medium text-muted-foreground">
            Deep dive into your financial habits.
          </p>
        </motion.div>

        <motion.div variants={itemVariants} className="flex flex-wrap items-center gap-3">
          <div className="relative group">
            <select
              value={yearParam}
              onChange={(e) => updateFilter('year', e.target.value)}
              className="appearance-none bg-background border border-border hover:border-primary/50 text-foreground text-sm rounded-xl px-4 py-2.5 pr-10 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all cursor-pointer font-medium"
            >
              <option value="all">All Years</option>
              {years.filter(y => y !== 'all').map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground">
              <ChevronDown className="h-4 w-4" />
            </div>
          </div>

          <div className="relative group">
            <select
              value={monthParam}
              onChange={(e) => updateFilter('month', e.target.value)}
              disabled={yearParam === 'all' || relativeParam !== 'none'}
              className="appearance-none bg-background border border-border hover:border-primary/50 text-foreground text-sm rounded-xl px-4 py-2.5 pr-10 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all cursor-pointer font-medium disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <option value="all">All Months</option>
              {Array.from({ length: 12 }).map((_, i) => (
                <option key={i} value={String(i)}>{monthName(i)}</option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground">
              <ChevronDown className="h-4 w-4" />
            </div>
          </div>

          <div className="relative group">
            <select
              value={relativeParam}
              onChange={(e) => updateFilter('relative', e.target.value)}
              className="appearance-none bg-background border border-border hover:border-primary/50 text-foreground text-sm rounded-xl px-4 py-2.5 pr-10 focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all cursor-pointer font-medium"
            >
              <option value="none">Custom Range</option>
              <option value="this_week">This Week</option>
              <option value="this_month">This Month</option>
              <option value="last_30">Last 30 Days</option>
              <option value="last_90">Last 90 Days</option>
              <option value="last_180">Last 6 Months</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-muted-foreground">
              <ChevronDown className="h-4 w-4" />
            </div>
          </div>
        </motion.div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4 auto-rows-[minmax(320px,auto)]">
        <motion.div variants={itemVariants} className="lg:col-span-2 lg:row-span-1">
          <ExpandableCard id="income-expense" title="Income vs Expense" className="h-[360px] lg:h-[400px] min-h-[360px]">
            {({ isExpanded }) => (
              <MonthlyComparison
                transactions={filteredTransactions}
                yearParam={yearParam}
                monthParam={monthParam}
                relativeParam={relativeParam}
                isExpanded={isExpanded}
              />
            )}
          </ExpandableCard>
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-2 lg:row-span-1">
          <ExpandableCard id="subscriptions" title="Subscription Radial" className="h-[320px] lg:h-[400px] min-h-[320px]">
            {({ isExpanded }) => (
              <SubscriptionRadar transactions={filteredTransactions} isExpanded={isExpanded} />
            )}
          </ExpandableCard>
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-2 lg:row-span-1">
          <ExpandableCard id="categories" title="Category Distribution" className="h-[320px] lg:h-[400px] min-h-[320px]">
            {({ isExpanded }) => (
              <CategoryDistribution transactions={filteredTransactions} isExpanded={isExpanded} />
            )}
          </ExpandableCard>
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-2 lg:row-span-1">
          <ExpandableCard id="merchants" title="Merchant Leaderboard" className="h-[320px] lg:h-[400px] min-h-[320px]">
            {({ isExpanded }) => (
              <MerchantLeaderboard transactions={filteredTransactions} isExpanded={isExpanded} />
            )}
          </ExpandableCard>
        </motion.div>
      </div>
    </motion.div>
  );
}

export default function AnalyticsPage() {
  return (
    <Suspense fallback={<div className="flex h-full items-center justify-center p-8"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>}>
      <AnalyticsContent />
    </Suspense>
  );
}
