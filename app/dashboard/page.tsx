"use client";

import { useEffect, useState, useMemo } from "react";
import {
  ArrowUpRight,
  Loader2,
  Activity,
  Zap,
  ShoppingBag,
  TrendingDown,
  Flame,
  ArrowRight
} from "lucide-react";
import { motion, Variants } from "framer-motion";
import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie
} from "recharts";
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
  merchant_name?: string;
};

type TrendData = {
  date: string;
  amount: number;
  fullDate: string;
};

type CategoryStat = {
  name: string;
  value: number; // Recharts uses 'value'
  color: string;
};

const OVERVIEW_CACHE_TTL_MS = 60 * 1000;

export default function OverviewPage() {
  const router = useRouter();
  const [data, setData] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState("there");
  const [stats, setStats] = useState({
    weeklyExpenses: 0,
    dailyAverage: 0,
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

      const cacheKey = `overview-cache:${user.id}`;
      const cachedRaw = sessionStorage.getItem(cacheKey);
      if (cachedRaw) {
        try {
          const cached = JSON.parse(cachedRaw) as {
            timestamp: number;
            rows: Transaction[];
            stats: { weeklyExpenses: number; dailyAverage: number };
          };
          if (Date.now() - cached.timestamp < OVERVIEW_CACHE_TTL_MS) {
            setData(cached.rows);
            setStats(cached.stats);
            setLoading(false);
          }
        } catch {
          // Ignore bad cache and continue.
        }
      }

      const { data: txData, error: txError } = await supabase
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

      const rows = (txData ?? []) as Transaction[];
      setData(rows);

      // --- Calculate Stats ---
      let weeklyExpenses = 0;
      const now = new Date();
      const oneWeekAgo = new Date();
      oneWeekAgo.setDate(now.getDate() - 7);

      for (const tx of rows) {
        const amount = Number(tx.amount || 0);
        const txDate = new Date(tx.transaction_date);

        // Weekly Expenses (Last 7 Days)
        if (amount < 0 && txDate >= oneWeekAgo && txDate <= now) {
          weeklyExpenses += Math.abs(amount);
        }
      }

      setStats({
        weeklyExpenses,
        dailyAverage: weeklyExpenses / 7,
      });
      sessionStorage.setItem(
        cacheKey,
        JSON.stringify({
          timestamp: Date.now(),
          rows,
          stats: {
            weeklyExpenses,
            dailyAverage: weeklyExpenses / 7,
          },
        }),
      );
      setLoading(false);
    };

    fetchData();
  }, [router]);

  // Derived Data: Spending Trends (Last 7 Days)
  const trendData: TrendData[] = useMemo(() => {
    if (data.length === 0) return Array(7).fill({ date: "", amount: 0, fullDate: "" });

    const last7Days = [];
    const today = new Date();
    const spendingByDate = new Map<string, number>();

    data.forEach(tx => {
      const amount = Number(tx.amount);
      if (amount < 0) {
        const dateStr = new Date(tx.transaction_date).toISOString().split('T')[0];
        const current = spendingByDate.get(dateStr) || 0;
        spendingByDate.set(dateStr, current + Math.abs(amount));
      }
    });

    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(today.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const spend = spendingByDate.get(dateStr) || 0;

      last7Days.push({
        date: d.toLocaleDateString('en-IN', { weekday: 'short' }), // Mon, Tue
        fullDate: d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
        amount: spend,
      });
    }

    return last7Days;
  }, [data]);

  // Derived Data: Top Categories (This Month) for Donut
  const topCategories: CategoryStat[] = useMemo(() => {
    const spendingMap = new Map<string, number>();
    const now = new Date();

    data.forEach(tx => {
      const amount = Number(tx.amount);
      const d = new Date(tx.transaction_date);
      if (amount < 0 && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()) {
        const absAmount = Math.abs(amount);
        const cat = tx.category || "Uncategorized";
        spendingMap.set(cat, (spendingMap.get(cat) || 0) + absAmount);
      }
    });

    const sorted = Array.from(spendingMap.entries())
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4);

    const colors = ["#3B82F6", "#8B5CF6", "#EC4899", "#10B981"]; // Blue, Purple, Pink, Emerald

    return sorted.map(([name, value], index) => ({
      name,
      value,
      color: colors[index % colors.length]
    }));
  }, [data]);

  // Derived Data: Largest Splurges (This Month)
  const splurges = useMemo(() => {
    return data
      .filter(tx => {
        const d = new Date(tx.transaction_date);
        const now = new Date();
        return Number(tx.amount) < 0 && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
      })
      .sort((a, b) => Math.abs(Number(b.amount)) - Math.abs(Number(a.amount)))
      .slice(0, 3);
  }, [data]);


  if (loading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Loader2 className="h-12 w-12 animate-spin text-blue-500" />
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
      className="flex h-full flex-col gap-6 overflow-hidden p-1"
    >
      <motion.div variants={itemVariants} className="flex-shrink-0 mb-2 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-black text-white tracking-tight">
            Hi, <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-emerald-400">{displayName}</span>
          </h1>
          <p className="text-sm text-slate-400">Your weekly spending snapshot.</p>
        </div>
      </motion.div>

      {/* Empty State Check */}
      {data.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex-1 flex flex-col items-center justify-center rounded-[2rem] border border-white/5 bg-[#0B1221] p-12 text-center shadow-xl relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-slush-gradient opacity-10"></div>
          <div className="relative z-10 max-w-lg">
            <motion.div
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              className="w-48 h-48 bg-gray-800/50 rounded-full mx-auto mb-8 flex items-center justify-center border border-white/10 shadow-2xl relative"
            >
              <div className="absolute inset-0 rounded-full bg-blue-500/10 animate-ping"></div>
              <Flame size={64} className="text-blue-400" />
            </motion.div>

            <h2 className="text-3xl font-black text-white mb-4">Welcome to SpendSmart!</h2>
            <p className="text-gray-400 text-lg mb-8">
              Your financial dashboard is currently empty. Add your first transaction to unlock powerful insights and visualizations.
            </p>

            <div className="flex justify-center gap-4">
              {/* We could route to transactions or open a modal. For now, route to transactions. */}
              <button
                onClick={() => router.push('/dashboard/transactions')}
                className="px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 rounded-2xl font-bold text-white shadow-lg shadow-blue-500/25 hover:scale-105 transition-transform flex items-center gap-2"
              >
                <ShoppingBag size={20} />
                Add Transaction
              </button>
            </div>
          </div>
        </motion.div>
      ) : (
        <>
          {/* Row 1: Weekly Expenses, Categories, Splurges */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

            {/* 1. Weekly Expenses Card (Bright Red) */}
            <motion.div
              variants={itemVariants}
              whileHover={{ scale: 1.02 }}
              className="rounded-[2rem] bg-gradient-to-br from-[#EF4444] to-[#B91C1C] p-6 text-white shadow-xl shadow-red-900/20 relative overflow-hidden group flex flex-col justify-between"
            >
              <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity duration-500">
                <ArrowUpRight size={100} />
              </div>

              <div className="relative z-10">
                <div className="flex items-center gap-2 mb-1">
                  <div className="p-1.5 rounded-full bg-white/20 backdrop-blur-sm">
                    <TrendingDown size={14} className="text-white" />
                  </div>
                  <span className="text-[10px] font-bold uppercase tracking-wider text-white/90">Last 7 Days</span>
                </div>
                <h2 className="text-3xl font-mono font-bold tracking-tighter mt-2">
                  ₹{stats.weeklyExpenses.toLocaleString("en-IN")}
                </h2>
              </div>

              <div className="relative z-10 mt-3 pt-3 border-t border-white/20">
                <div className="flex justify-between items-end">
                  <div>
                    <p className="text-[10px] font-bold text-white/80 uppercase mb-0.5">Daily Average</p>
                    <p className="text-lg font-mono font-bold">₹{Math.round(stats.dailyAverage).toLocaleString("en-IN")}</p>
                  </div>
                  <div className="text-[10px] font-medium bg-white/20 px-2 py-0.5 rounded text-white/90">
                    Avg / Day
                  </div>
                </div>
              </div>
            </motion.div>

            {/* 2. Top Categories (Donut Chart) */}
            <motion.section
              variants={itemVariants}
              className="rounded-[2rem] border border-white/5 bg-[#0B1221] p-5 shadow-xl flex flex-row items-center gap-4 relative overflow-hidden"
            >
              <div className="flex-1 min-w-0 flex flex-col justify-center">
                <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-1">
                  <ShoppingBag size={14} className="text-pink-500" />
                  Top Categories
                </h3>
                <span className="text-[10px] font-bold uppercase text-gray-500 mb-2 block">This Month</span>
                <div className="flex flex-col gap-1.5">
                  {topCategories.slice(0, 3).map((cat, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: cat.color }} />
                      <span className="text-[11px] text-gray-400 truncate font-medium">{cat.name}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="w-[120px] h-[120px] relative flex-shrink-0">
                {topCategories.length === 0 ? (
                  <p className="text-gray-500 text-[10px] italic absolute inset-0 flex items-center justify-center">No data</p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={topCategories}
                        cx="50%"
                        cy="50%"
                        innerRadius={35}
                        outerRadius={55}
                        paddingAngle={5}
                        dataKey="value"
                        stroke="none"
                      >
                        {topCategories.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ backgroundColor: '#1F2937', borderColor: '#374151', borderRadius: '8px', padding: '4px 8px' }}
                        itemStyle={{ color: '#fff', fontSize: '10px' }}
                        formatter={(value: any) => `₹${(value || 0).toLocaleString()}`}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </motion.section>

            {/* 3. Big Splurges (List) */}
            <motion.section
              variants={itemVariants}
              className="rounded-[2rem] border border-white/5 bg-[#0B1221] p-5 shadow-xl flex flex-col"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Zap size={14} className="text-yellow-500" />
                  Big Splurges
                </h3>
              </div>

              <div className="space-y-2 flex-1 overflow-y-auto custom-scrollbar pr-1">
                {splurges.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-gray-500 text-xs italic">No large purchases.</div>
                ) : (
                  splurges.map((tx, i) => (
                    <motion.div
                      whileHover={{ x: 2, backgroundColor: 'rgba(255,255,255,0.05)' }}
                      key={tx.id}
                      className="flex items-center gap-3 p-2 rounded-lg border border-transparent transition-all cursor-pointer group"
                    >
                      <div className="h-6 w-6 rounded-md bg-white/5 flex items-center justify-center font-bold text-[10px] shrink-0 text-white">
                        {i + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-bold text-white truncate group-hover:text-red-400 transition-colors">{tx.description || "Purchase"}</p>
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-xs font-mono font-bold text-red-400">₹{Math.abs(Number(tx.amount)).toLocaleString("en-IN")}</p>
                      </div>
                    </motion.div>
                  ))
                )}
              </div>
            </motion.section>
          </div>

          {/* Row 2: Full Width Spending Trends */}
          <motion.section
            variants={itemVariants}
            className="flex-1 min-h-[380px] rounded-[2rem] border border-white/5 bg-[#0B1221] p-6 shadow-xl relative overflow-hidden flex flex-col"
          >
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-white flex items-center gap-2">
                  <Activity size={20} className="text-blue-500" />
                  Spending Trends
                </h3>
                <p className="text-xs text-gray-500 mt-1 ml-7">Your daily spending activity for the last week</p>
              </div>
              <div className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-500/10 rounded-full border border-blue-500/20">
                  <div className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                  <span className="text-[10px] font-bold text-blue-400 uppercase">Live Data</span>
                </div>
              </div>
            </div>

            <div className="flex-1 w-full min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#60A5FA" stopOpacity={0.8} />
                      <stop offset="100%" stopColor="#3B82F6" stopOpacity={0.3} />
                    </linearGradient>
                    <linearGradient id="barHover" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#F472B6" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#DB2777" stopOpacity={0.5} />
                    </linearGradient>
                  </defs>
                  <Tooltip
                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        return (
                          <div className="bg-[#1F2937] border border-white/10 p-3 rounded-xl shadow-xl backdrop-blur-md bg-opacity-90">
                            <p className="text-gray-400 text-xs font-medium mb-1">{payload[0].payload.fullDate}</p>
                            <p className="text-white font-bold font-mono text-lg">₹{Number(payload[0].value).toLocaleString()}</p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: '#6B7280', fontSize: 12, fontWeight: 600 }}
                    dy={10}
                  />
                  <Bar
                    dataKey="amount"
                    radius={[6, 6, 6, 6]}
                    animationDuration={1500}
                  >
                    {trendData.map((entry, index) => (
                      <Cell
                        key={`cell-${index}`}
                        fill="url(#barGradient)"
                        className="hover:opacity-100 transition-all duration-300 hover:fill-[url(#barHover)] cursor-pointer" // Correct hover effect
                        style={{ outline: 'none' }}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </motion.section>
        </>
      )}
    </motion.div>
  );
}
