'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, Variants } from 'framer-motion';
import { Loader2, Activity } from 'lucide-react';
import { supabase } from '../../../lib/supabase/client';
import { accountsApi, type Transaction } from '../../../lib/api/client';

import { MonthlyComparison } from './components/MonthlyComparison';
import { SpendingHeatmap } from './components/SpendingHeatmap';
import { CategoryDistribution } from './components/CategoryDistribution';
import { MerchantLeaderboard } from './components/MerchantLeaderboard';
import { AnalyticsEmptyState } from './components/AnalyticsEmptyState';
import { getCachedData, setCachedData } from '../../../lib/utils/cache';

const ANALYTICS_CACHE_TTL_MS = 60 * 60 * 1000; // 1 hour cache

export default function AnalyticsPage() {
  const router = useRouter();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

        const cacheKey = `analytics-cache:${user.id}`;
        const cachedData = getCachedData<Transaction[]>(cacheKey, ANALYTICS_CACHE_TTL_MS);

        if (cachedData) {
          if (mounted) {
            setTransactions(cachedData);
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

        // Single request: last 12 months, up to 500 transactions.
        // Avoids multi-round-trip cursor loop that causes 7+ second load times
        // and is sensitive to backend hot-reloads during development.
        const twelveMonthsAgo = new Date();
        twelveMonthsAgo.setFullYear(twelveMonthsAgo.getFullYear() - 1);
        const response = await accountsApi.getTransactions(session.access_token, {
          limit: 500,
          date_from: twelveMonthsAgo.toISOString().split('T')[0],
        });

        if (!mounted) return;

        setTransactions(response.items);
        setCachedData(cacheKey, response.items);
      } catch (err: unknown) {
        if (!mounted) return;
        const message = err instanceof Error ? err.message : 'Failed to load analytics data.';
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

  // Filter for valid expenses only for deeper analysis if needed,
  // but components generally handle their own filtering.
  // Passing all transactions allows components to decide (e.g. income vs expense)

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="mx-auto flex w-full max-w-7xl flex-col gap-4 p-2 md:p-4"
    >
      <motion.div variants={itemVariants} className="flex flex-col gap-1">
        <h1 className="text-3xl font-black text-foreground tracking-tight">Analytics</h1>
        <p className="text-sm font-medium text-muted-foreground">
          Deep dive into your spending habits.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        <motion.div variants={itemVariants} className="lg:col-span-4 lg:row-span-1 min-h-0">
          <MonthlyComparison transactions={transactions as any} />
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-8 lg:row-span-1 min-h-0">
          <SpendingHeatmap transactions={transactions as any} />
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-5 lg:row-span-1 min-h-0">
          <CategoryDistribution transactions={transactions as any} />
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-7 lg:row-span-1 min-h-0">
          <MerchantLeaderboard transactions={transactions as any} />
        </motion.div>
      </div>
    </motion.div>
  );
}
