"use client";

import { useEffect, useState, useMemo } from "react";
import { ArrowDownLeft, ArrowUpRight, CreditCard, Loader2, TrendingUp, Wallet, Activity } from "lucide-react";
import { motion, Variants } from "framer-motion";
import { useRouter } from "next/navigation";
import { supabase } from "../../lib/supabase/client";

function firstNameFromDisplayName(value: string): string {
  const cleaned = value.trim().replace(/\s+/g, " ");
  if (!cleaned) return "there";
  return cleaned.split(" ")[0] || "there";
}

// Types
type Transaction = {
  id: string;
  description: string;
  amount: number;
  transaction_date: string;
  category: string;
  type?: string;
};

type TrendData = {
  date: string;
  amount: number;
  height: number; // 0-100 for css height
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
    trendDirection: "up", // or 'down'
    trendPercentage: 0
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
      const fallbackName = user.email?.split("@")[0] ?? "there";
      setDisplayName(firstNameFromDisplayName(fullName || fallbackName));

      const { data, error: txError } = await supabase
        .from("transactions")
        .select("*")
        .eq("user_id", user.id)
        .order("transaction_date", { ascending: false });

      if (txError) {
        console.error("Error fetching transactions:", txError);
        setError("Unable to load financial data.");
        setLoading(false);
        return;
      }

      const rows = (data ?? []) as Transaction[];
      setTransactions(rows);

      let netWorth = 0;
      let income = 0;
      let expenses = 0;
      const now = new Date();
      const currentMonth = now.getMonth();
      const currentYear = now.getFullYear();

      for (const tx of rows) {
        const amount = Number(tx.amount || 0);
        const txDate = new Date(tx.transaction_date);

        netWorth += amount;
        if (txDate.getMonth() === currentMonth && txDate.getFullYear() === currentYear) {
          if (amount >= 0) {
            income += amount;
          } else {
            expenses += Math.abs(amount);
          }
        }
      }

      setStats({
        netWorth,
        income,
        expenses,
        trendDirection: netWorth >= 0 ? "up" : "down",
        trendPercentage: 2.4 // Placeholder or calculate real DoD/MoM later
      });
      setLoading(false);
    };

    fetchData();
  }, [router]);

  // 3. Generate Spending Trends Data (Last 10 Days)
  const trendData: TrendData[] = useMemo(() => {
    if (transactions.length === 0) return Array(10).fill({ date: "", amount: 0, height: 0 });

    const last10Days = [];
    const today = new Date();

    // Create map of date -> total spending (negative amounts)
    const spendingByDate = new Map<string, number>();

    transactions.forEach(tx => {
      const amount = Number(tx.amount);
      if (amount < 0) {
        const dateStr = new Date(tx.transaction_date).toISOString().split('T')[0]; // YYYY-MM-DD
        const current = spendingByDate.get(dateStr) || 0;
        spendingByDate.set(dateStr, current + Math.abs(amount));
      }
    });

    let maxSpend = 0;

    for (let i = 9; i >= 0; i--) {
      const d = new Date();
      d.setDate(today.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const spend = spendingByDate.get(dateStr) || 0;
      if (spend > maxSpend) maxSpend = spend;

      last10Days.push({
        date: d.toLocaleDateString('en-IN', { weekday: 'short' }),
        amount: spend,
        height: 0 // calculate after
      });
    }

    // Normalize heights to 0-100%
    return last10Days.map(d => ({
      ...d,
      height: maxSpend > 0 ? (d.amount / maxSpend) * 100 : 0
    }));

  }, [transactions]);

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
        <div className="rounded-2xl border border-red-500/20 bg-red-500/10 p-6 text-red-200 backdrop-blur-md">
          <Activity className="mx-auto mb-2 h-8 w-8 text-red-400" />
          <p>{error}</p>
          <button onClick={() => window.location.reload()} className="mt-4 rounded-lg bg-red-500/20 px-4 py-2 hover:bg-red-500/30">Retry</button>
        </div>
      </div>
    );
  }

  // Animation Variants
  const containerVariants: Variants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVariants: Variants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { type: "spring", stiffness: 300, damping: 24 }
    }
  };

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="flex h-full flex-col gap-6 overflow-hidden"
    >
      <motion.div variants={itemVariants} className="flex-shrink-0 flex justify-between items-end">
        <div>
          <h1 className="text-4xl font-black text-white tracking-tight">
            Welcome back, <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">{displayName}</span>
          </h1>
          <p className="text-base text-slate-400 mt-1">Here&apos;s what&apos;s happening with your money today.</p>
        </div>
        <div className="hidden md:flex items-center gap-2 text-sm font-medium text-slate-400 bg-white/5 px-4 py-2 rounded-full border border-white/5">
          <span>📅 {new Date().toLocaleDateString('en-IN', { month: 'long', year: 'numeric' })}</span>
        </div>
      </motion.div>

      {/* Top Stats Cards */}
      <div className="grid flex-shrink-0 grid-cols-1 gap-5 md:grid-cols-4">
        {/* Net Worth - Large Card */}
        <motion.div
          variants={itemVariants}
          whileHover={{ scale: 1.02, transition: { duration: 0.2 } }}
          className="relative min-w-0 md:col-span-2 rounded-[2.5rem] border border-white/10 bg-gradient-to-br from-[#0B1221] to-[#151C2F] p-8 shadow-2xl overflow-hidden group"
        >
          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity duration-500">
            <Wallet size={180} />
          </div>
          <div className="relative z-10">
            <div className="mb-2 text-gray-400 font-medium flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
              Total Net Worth
            </div>
            <h2 className="mb-4 font-mono text-5xl font-bold tracking-tighter text-white">
              ₹{stats.netWorth.toLocaleString("en-IN")}
            </h2>
            <div className={`inline-flex items-center gap-2 rounded-full px-4 py-1.5 text-sm font-bold border ${stats.netWorth >= 0
              ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
              : "bg-red-500/10 text-red-400 border-red-500/20"
              }`}>
              <TrendingUp size={16} />
              <span>{stats.netWorth >= 0 ? "+2.4%" : "-1.2%"} from last month</span>
            </div>
          </div>
        </motion.div>

        {/* Income Card */}
        <motion.div
          variants={itemVariants}
          whileHover={{ scale: 1.05, rotate: -1, transition: { type: "spring", stiffness: 400, damping: 10 } }}
          className="flex cursor-pointer flex-col justify-between rounded-[2.5rem] bg-[#10B981] p-6 text-black shadow-lg hover:shadow-emerald-500/20 transition-shadow"
        >
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-black/10 backdrop-blur-sm">
            <ArrowDownLeft size={24} className="text-black" />
          </div>
          <div>
            <p className="text-sm font-bold text-black/60 uppercase tracking-wider">Income</p>
            <h3 className="mt-1 font-mono text-3xl font-bold text-black truncate">₹{stats.income.toLocaleString("en-IN")}</h3>
          </div>
        </motion.div>

        {/* Expenses Card */}
        <motion.div
          variants={itemVariants}
          whileHover={{ scale: 1.05, rotate: 1, transition: { type: "spring", stiffness: 400, damping: 10 } }}
          className="flex cursor-pointer flex-col justify-between rounded-[2.5rem] bg-[#EF4444] p-6 text-white shadow-lg hover:shadow-red-500/20 transition-shadow"
        >
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-white/20 backdrop-blur-sm">
            <ArrowUpRight size={24} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-bold text-white/80 uppercase tracking-wider">Expenses</p>
            <h3 className="mt-1 font-mono text-3xl font-bold text-white truncate">₹{stats.expenses.toLocaleString("en-IN")}</h3>
          </div>
        </motion.div>
      </div>

      {/* Bottom Section - Charts & Transactions */}
      <div className="flex min-h-0 min-w-0 flex-1 gap-6 flex-col md:flex-row">
        {/* Spending Trends */}
        <motion.section
          variants={itemVariants}
          className="flex min-h-0 min-w-0 flex-[2] flex-col rounded-[2.5rem] border border-white/5 bg-[#0B1221] p-6 shadow-xl relative overflow-hidden"
        >
          <div className="absolute top-0 right-0 w-full h-full bg-gradient-to-b from-blue-500/5 to-transparent pointer-events-none" />
          <div className="mb-6 flex items-center justify-between relative z-10">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <Activity size={20} className="text-blue-500" />
              Spending Trends
            </h3>
            <div className="rounded-xl border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-bold text-gray-400">Last 10 Days</div>
          </div>

          <div className="flex min-h-0 flex-1 items-end gap-3 px-2 pb-2 relative z-10">
            {trendData.map((d, i) => (
              <div key={i} className="flex-1 flex flex-col justify-end gap-2 group h-full">
                <div className="h-full flex items-end relative">
                  <motion.div
                    initial={{ height: 0 }}
                    animate={{ height: `${d.height || 5}%` }} // Ensure at least a sliver shows
                    transition={{ delay: 0.3 + i * 0.05, duration: 0.6, type: "spring" }}
                    className="w-full rounded-t-xl bg-gradient-to-t from-blue-600 to-blue-400 opacity-60 group-hover:opacity-100 transition-opacity relative"
                  >
                    <div className="absolute -top-10 left-1/2 -translate-x-1/2 bg-white text-black text-xs font-bold px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap z-20 pointer-events-none">
                      ₹{d.amount}
                    </div>
                  </motion.div>
                </div>
                <div className="text-center text-[10px] uppercase font-bold text-gray-500 group-hover:text-blue-400 transition-colors">
                  {d.date}
                </div>
              </div>
            ))}
          </div>
        </motion.section>

        {/* Recent Transactions */}
        <motion.section
          variants={itemVariants}
          className="flex min-h-0 min-w-0 flex-1 flex-col rounded-[2.5rem] border border-white/5 bg-[#0B1221] p-6 shadow-xl"
        >
          <h3 className="mb-6 text-xl font-bold text-white flex items-center gap-2">
            <CreditCard size={20} className="text-purple-500" />
            Recent Activity
          </h3>
          <div className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-2 custom-scrollbar">
            {transactions.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-slate-500 gap-2">
                <div className="p-4 rounded-full bg-white/5"><Wallet size={24} /></div>
                <p>No transactions found.</p>
              </div>
            ) : (
              transactions.map((tx, i) => {
                const amount = Number(tx.amount || 0);
                const isIncome = amount >= 0;
                return (
                  <motion.div
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.1 * i }}
                    key={tx.id}
                    className="flex items-center justify-between rounded-2xl p-4 bg-white/5 border border-white/5 hover:bg-white/10 hover:border-white/20 transition-all cursor-pointer group"
                  >
                    <div className="flex items-center gap-4">
                      <div className={`flex h-12 w-12 items-center justify-center rounded-2xl text-lg ${isIncome ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
                        }`}>
                        {isIncome ? <ArrowDownLeft size={20} /> : <ArrowUpRight size={20} />}
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-bold text-white group-hover:text-blue-400 transition-colors max-w-[120px]">
                          {tx.description || "Transaction"}
                        </p>
                        <p className="text-xs text-slate-400 font-medium">
                          {new Date(tx.transaction_date).toLocaleDateString("en-IN", {
                            day: "numeric",
                            month: "short",
                          })} · {tx.category}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className={`font-mono text-base font-bold block ${isIncome ? "text-emerald-400" : "text-white"}`}>
                        {isIncome ? "+" : ""}₹{Math.abs(amount).toLocaleString("en-IN")}
                      </span>
                    </div>
                  </motion.div>
                );
              })
            )}
          </div>
        </motion.section>
      </div>
    </motion.div>
  );
}
