'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion, Variants } from 'framer-motion';
import { Loader2, Activity } from 'lucide-react';
import { supabase } from '../../../lib/supabase/client';

import { MonthlyComparison } from './components/MonthlyComparison';
import { SpendingHeatmap } from './components/SpendingHeatmap';
import { CategoryDistribution } from './components/CategoryDistribution';
import { MerchantLeaderboard } from './components/MerchantLeaderboard';
import { AnalyticsEmptyState } from './components/AnalyticsEmptyState';

// Types
type Transaction = {
  id: string;
  description: string;
  amount: number;
  transaction_date: string;
  category: string;
  type?: 'credit' | 'debit';
  merchant_name?: string;
  status?: string;
  payment_method?: string;
};

const ANALYTICS_CACHE_TTL_MS = 60 * 1000; // 1 minute cache

export default function AnalyticsPage() {
  const router = useRouter();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
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
        const cachedRaw = sessionStorage.getItem(cacheKey);
        if (cachedRaw) {
          try {
            const cached = JSON.parse(cachedRaw) as { timestamp: number; rows: Transaction[] };
            if (Date.now() - cached.timestamp < ANALYTICS_CACHE_TTL_MS) {
              setTransactions(cached.rows);
              setLoading(false);
            }
          } catch {
            /* ignore */
          }
        }

        const { data: txData, error: txError } = await supabase
          .from('transactions')
          .select('*')
          .eq('user_id', user.id)
          .order('transaction_date', { ascending: false });

        if (txError) throw txError;

        if (txData) {
          setTransactions(txData);
          sessionStorage.setItem(
            cacheKey,
            JSON.stringify({
              timestamp: Date.now(),
              rows: txData,
            })
          );
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'Failed to load analytics data.';
        setError(message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
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
      className="mx-auto flex h-full min-h-0 w-full max-w-7xl flex-col gap-4 p-2 md:p-4"
    >
      <motion.div variants={itemVariants} className="flex flex-col gap-1">
        <h1 className="text-3xl font-black text-foreground tracking-tight">Analytics</h1>
        <p className="text-sm font-medium text-muted-foreground">
          Deep dive into your spending habits.
        </p>
      </motion.div>

      <div className="grid flex-1 min-h-0 grid-cols-1 gap-4 lg:grid-cols-12 lg:grid-rows-2">
        <motion.div variants={itemVariants} className="lg:col-span-4 lg:row-span-1 min-h-0">
          <MonthlyComparison transactions={transactions} />
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-8 lg:row-span-1 min-h-0">
          <SpendingHeatmap transactions={transactions} />
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-5 lg:row-span-1 min-h-0">
          <CategoryDistribution transactions={transactions} />
        </motion.div>

        <motion.div variants={itemVariants} className="lg:col-span-7 lg:row-span-1 min-h-0">
          <MerchantLeaderboard transactions={transactions} />
        </motion.div>
      </div>
    </motion.div>
  );
}
