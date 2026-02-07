"use client";

import { useEffect, useState } from "react";
import { ArrowDownLeft, ArrowUpRight, CreditCard, Loader2, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase/client";

type Transaction = {
  id: string;
  description: string;
  amount: number;
  transaction_date: string;
  category: string;
};

export default function OverviewPage() {
  const router = useRouter();
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("there");
  const [stats, setStats] = useState({
    netWorth: 0,
    income: 0,
    expenses: 0,
  });

  useEffect(() => {
    const fetchData = async () => {
      const {
        data: { user },
        error: userError,
      } = await supabase.auth.getUser();

      if (userError || !user) {
        router.replace("/login");
        return;
      }

      const fullName = user.user_metadata?.full_name as string | undefined;
      const name = (fullName || user.email?.split("@")[0] || "there").split(" ")[0];
      setDisplayName(name);

      const { data, error: txError } = await supabase
        .from("transactions")
        .select("id,description,amount,transaction_date,category")
        .eq("user_id", user.id)
        .order("transaction_date", { ascending: false })
        .limit(20);

      if (txError) {
        setError("Unable to load overview right now.");
        setLoading(false);
        return;
      }

      const rows = (data ?? []) as Transaction[];
      setTransactions(rows);

      let netWorth = 0;
      let income = 0;
      let expenses = 0;

      for (const tx of rows) {
        const amount = Number(tx.amount || 0);
        netWorth += amount;
        if (amount >= 0) {
          income += amount;
        } else {
          expenses += Math.abs(amount);
        }
      }

      setStats({ netWorth, income, expenses });
      setLoading(false);
    };

    fetchData();
  }, [router]);

  if (loading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  if (error) {
    return <div className="rounded-2xl border border-red-500/40 bg-red-500/10 p-5 text-red-100">{error}</div>;
  }

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_auto_minmax(0,1fr)] gap-6 overflow-hidden">
      <div>
        <h1 className="text-3xl font-black text-white">Good evening, {displayName}</h1>
        <p className="text-sm text-slate-400">Track activity, review transactions, and monitor your money movement.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="min-w-0 md:col-span-2 rounded-3xl border border-white/5 bg-gradient-to-br from-secondary to-gray-900 p-6 shadow-slush"
        >
          <div className="mb-2 text-gray-400">Total Net Worth</div>
          <h2 className="mb-3 font-mono text-4xl font-bold tracking-tight text-white">₹{stats.netWorth.toLocaleString("en-IN")}</h2>
          <div className="inline-flex items-center gap-2 rounded-full bg-success/10 px-3 py-1 text-success">
            <TrendingUp size={16} />
            <span className="text-sm font-bold">Live snapshot</span>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="flex cursor-pointer flex-col justify-between rounded-3xl bg-[#10B981] p-5 text-black shadow-slush-sm"
        >
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/20">
            <ArrowDownLeft size={20} />
          </div>
          <div>
            <p className="text-sm font-medium text-black/70">Income</p>
            <h3 className="mt-1 font-mono text-[2rem] font-bold text-white">₹{stats.income.toLocaleString("en-IN")}</h3>
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="flex cursor-pointer flex-col justify-between rounded-3xl bg-[#EF4444] p-5 text-white shadow-slush-sm"
        >
          <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-white/20">
            <ArrowUpRight size={20} />
          </div>
          <div>
            <p className="text-sm font-medium text-white/80">Expenses</p>
            <h3 className="mt-1 font-mono text-[2rem] font-bold">₹{stats.expenses.toLocaleString("en-IN")}</h3>
          </div>
        </motion.div>
      </div>

      <div className="grid min-h-0 grid-cols-1 gap-4 md:h-[280px] md:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section className="flex min-h-0 min-w-0 flex-col rounded-3xl border border-white/5 bg-secondary p-5 shadow-md md:h-[280px]">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-bold text-white">Spending Trends</h3>
            <div className="rounded-lg border border-white/10 bg-background px-3 py-1 text-sm text-gray-400">Last 30 Days</div>
          </div>
          <div className="flex min-h-0 flex-1 items-end gap-2 border-b border-l border-white/5 px-4 pb-3">
            {[40, 65, 30, 80, 55, 90, 45, 70, 60, 85].map((h, i) => (
              <motion.div
                key={i}
                initial={{ height: 0 }}
                animate={{ height: `${h}%` }}
                transition={{ delay: 0.2 + i * 0.04, duration: 0.4 }}
                className="flex-1 rounded-t-sm bg-primary/30"
              />
            ))}
          </div>
        </section>

        <section className="flex min-h-0 min-w-0 flex-col rounded-3xl border border-white/5 bg-secondary p-5 shadow-md md:h-[280px]">
          <h3 className="mb-4 text-lg font-bold text-white">Recent Transactions</h3>
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto pr-1">
            {transactions.length === 0 ? (
              <p className="py-10 text-center text-gray-500">No transactions found.</p>
            ) : (
              transactions.slice(0, 10).map((tx) => {
                const amount = Number(tx.amount || 0);
                return (
                  <div key={tx.id} className="flex items-center justify-between rounded-xl p-3 hover:bg-white/5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-background text-sm">
                        <CreditCard size={16} />
                      </div>
                      <div>
                        <p className="max-w-[140px] truncate text-sm font-bold text-white">{tx.description || "Transaction"}</p>
                        <p className="text-xs text-gray-400">
                          {new Date(tx.transaction_date).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                          })}
                        </p>
                      </div>
                    </div>
                    <span className={`font-mono text-sm font-bold ${amount >= 0 ? "text-success" : "text-white"}`}>
                      {amount >= 0 ? "+" : ""}₹{Math.abs(amount).toLocaleString("en-IN")}
                    </span>
                  </div>
                );
              })
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
