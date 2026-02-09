"use client";

import { useEffect, useState, useMemo } from "react";
import {
  ArrowUpRight,
  Loader2,
  Activity,
  Zap,
  ShoppingBag,
  TrendingDown,
  Flame
} from "lucide-react";
import { motion, Variants } from "framer-motion";
import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
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
  const [timeframe, setTimeframe] = useState<"weekly" | "monthly">("weekly");

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
          };
          if (Date.now() - cached.timestamp < OVERVIEW_CACHE_TTL_MS) {
            setData(cached.rows);
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
      sessionStorage.setItem(
        cacheKey,
        JSON.stringify({
          timestamp: Date.now(),
          rows,
        }),
      );
      setLoading(false);
    };

    fetchData();
  }, [router]);

  const periodExpenses = (() => {
    const now = new Date();

    return data.filter((tx) => {
      const amount = Number(tx.amount || 0);
      if (amount >= 0) return false;
      const dateObj = new Date(tx.transaction_date);
      if (Number.isNaN(dateObj.getTime())) return false;

      // Create a local date object (midnight) for comparison
      const txLocalTime = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate());

      if (timeframe === "weekly") {
        const oneWeekAgo = new Date(now);
        oneWeekAgo.setHours(0, 0, 0, 0);
        oneWeekAgo.setDate(now.getDate() - 6);
        return txLocalTime >= oneWeekAgo && txLocalTime <= now;
      }

      return txLocalTime.getMonth() === now.getMonth() && txLocalTime.getFullYear() === now.getFullYear();
    });
  })();

  const stats = useMemo(() => {
    const totalExpenses = periodExpenses.reduce((sum, tx) => sum + Math.abs(Number(tx.amount || 0)), 0);

    if (totalExpenses <= 0) {
      return {
        totalExpenses: 0,
        average: 0,
      };
    }

    let divisor = 1;

    if (timeframe === "weekly") {
      const activeDays = new Set<string>();
      for (const tx of periodExpenses) {
        const d = new Date(tx.transaction_date);
        if (Number.isNaN(d.getTime())) continue;
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, "0");
        const day = String(d.getDate()).padStart(2, "0");
        activeDays.add(`${y}-${m}-${day}`);
      }
      divisor = Math.max(activeDays.size, 1);
    } else {
      const activeWeeks = new Set<number>();
      for (const tx of periodExpenses) {
        const d = new Date(tx.transaction_date);
        if (Number.isNaN(d.getTime())) continue;
        const weekIndex = Math.floor((d.getDate() - 1) / 7);
        activeWeeks.add(weekIndex);
      }
      divisor = Math.max(activeWeeks.size, 1);
    }

    return {
      totalExpenses,
      average: totalExpenses / divisor,
    };
  }, [periodExpenses, timeframe]);

  // Derived Data: Spending Trends
  const trendData: TrendData[] = useMemo(() => {
    const today = new Date();
    const spendingByDate = new Map<string, number>();

    periodExpenses.forEach(tx => {
      const amount = Number(tx.amount);
      if (amount < 0) {
        // Use local YYYY-MM-DD key from the parsed date object
        const d = new Date(tx.transaction_date);
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const dateStr = `${y}-${m}-${day}`;
        const current = spendingByDate.get(dateStr) || 0;
        spendingByDate.set(dateStr, current + Math.abs(amount));
      }
    });

    if (timeframe === "weekly") {
      const last7Days = [];
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(today.getDate() - i);

        // Construct YYYY-MM-DD Key in Local Time
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const dateStr = `${y}-${m}-${day}`;

        const spend = spendingByDate.get(dateStr) || 0;

        last7Days.push({
          date: d.toLocaleDateString('en-IN', { weekday: 'short' }),
          fullDate: d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
          amount: spend,
        });
      }
      return last7Days;
    }

    // Monthly View: Full Month Weekly Buckets
    const weeklyBuckets: TrendData[] = [];
    const currentYear = today.getFullYear();
    const currentMonth = today.getMonth();

    // Start from the 1st of the month
    const cursor = new Date(currentYear, currentMonth, 1);
    const monthEnd = new Date(currentYear, currentMonth + 1, 0); // Last day of month

    let weekIndex = 1;

    while (cursor <= monthEnd) {
      const bucketStart = new Date(cursor);
      const bucketEnd = new Date(cursor);
      bucketEnd.setDate(cursor.getDate() + 6);

      // If bucket exceeds month, cap it visually but logic remains consistent
      const labelStart = bucketStart.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
      const labelEndRaw = bucketEnd > monthEnd ? monthEnd : bucketEnd;
      const labelEnd = labelEndRaw.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });

      let bucketSum = 0;

      // Iterate through days in this bucket
      for (let i = 0; i < 7; i++) {
        const d = new Date(bucketStart);
        d.setDate(bucketStart.getDate() + i);

        if (d.getMonth() === currentMonth) {
          const y = d.getFullYear();
          const m = String(d.getMonth() + 1).padStart(2, '0');
          const day = String(d.getDate()).padStart(2, '0');
          const key = `${y}-${m}-${day}`;
          bucketSum += spendingByDate.get(key) || 0;
        }
      }

      weeklyBuckets.push({
        date: `W${weekIndex}`,
        fullDate: `${labelStart} - ${labelEnd}`,
        amount: bucketSum,
      });

      cursor.setDate(cursor.getDate() + 7);
      weekIndex++;
    }

    return weeklyBuckets;
  }, [periodExpenses, timeframe]);

  // Derived Data: Top Categories for selected period
  const topCategories: CategoryStat[] = useMemo(() => {
    const spendingMap = new Map<string, number>();

    periodExpenses.forEach(tx => {
      const amount = Number(tx.amount);
      if (amount < 0) {
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
  }, [periodExpenses]);

  // Derived Data: Largest Splurges for selected period
  const splurges = useMemo(() => {
    return [...periodExpenses]
      .sort((a, b) => Math.abs(Number(b.amount)) - Math.abs(Number(a.amount)))
      .slice(0, 3);
  }, [periodExpenses]);


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
          <button onClick={() => window.location.reload()} className="mt-4 rounded-lg bg-destructive/20 px-4 py-2 hover:bg-destructive/30">Retry</button>
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
      className="flex h-full flex-col gap-6 overflow-hidden p-1 transition-colors duration-300"
    >
      <motion.div variants={itemVariants} className="flex-shrink-0 mb-2 flex justify-between items-end">
        <div>
          <h1 className="text-3xl font-black text-foreground tracking-tight">
            Hi, <span className="text-primary">{displayName}</span>
          </h1>
          <p className="text-sm text-muted-foreground">Your {timeframe} spending snapshot.</p>
        </div>
        <div className="flex items-center gap-1 rounded-2xl border border-border bg-card p-1 shadow-sm">
          {(["weekly", "monthly"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setTimeframe(mode)}
              className={`rounded-xl px-4 py-2 text-xs font-bold uppercase tracking-wide transition ${timeframe === mode
                ? "bg-primary text-primary-foreground shadow-lg shadow-blue-500/30"
                : "text-muted-foreground hover:bg-muted"
                }`}
            >
              {mode}
            </button>
          ))}
        </div>
      </motion.div>

      {/* Empty State Check */}
      {data.length === 0 ? (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="flex-1 flex flex-col items-center justify-center rounded-[2rem] border border-border bg-card p-12 text-center shadow-xl relative overflow-hidden"
        >
          <div className="absolute inset-0 bg-slush-gradient opacity-5"></div>
          <div className="relative z-10 max-w-lg">
            <motion.div
              animate={{ y: [0, -10, 0] }}
              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
              className="w-48 h-48 bg-muted rounded-full mx-auto mb-8 flex items-center justify-center border border-border shadow-2xl relative"
            >
              <div className="absolute inset-0 rounded-full bg-primary/10 animate-ping"></div>
              <Flame size={64} className="text-primary" />
            </motion.div>

            <h2 className="text-3xl font-black text-foreground mb-4">Welcome to SCALE!</h2>
            <p className="text-muted-foreground text-lg mb-8">
              Your financial dashboard is currently empty. Add your first transaction to unlock powerful insights and visualizations.
            </p>

            <div className="flex justify-center gap-4">
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

            {/* 1. Weekly Expenses Card (Bright Red - Keeping accent) */}
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
                  <span className="text-[10px] font-bold uppercase tracking-wider text-white/90">
                    {timeframe === "weekly" ? "Last 7 Days" : "This Month"}
                  </span>
                </div>
                <h2 className="text-3xl font-mono font-bold tracking-tighter mt-2">
                  ₹{stats.totalExpenses.toLocaleString("en-IN")}
                </h2>
              </div>

              <div className="relative z-10 mt-3 pt-3 border-t border-white/20">
                <div className="flex justify-between items-end">
                  <div>
                    <p className="text-[10px] font-bold text-white/80 uppercase mb-0.5">
                      {timeframe === "weekly" ? "Daily Average" : "Weekly Average"}
                    </p>
                    <p className="text-lg font-mono font-bold">₹{Math.round(stats.average).toLocaleString("en-IN")}</p>
                  </div>
                  <div className="text-[10px] font-medium bg-white/20 px-2 py-0.5 rounded text-white/90">
                    {timeframe === "weekly" ? "Avg / Day" : "Avg / Week"}
                  </div>
                </div>
              </div>
            </motion.div>

            {/* 2. Top Categories (Donut Chart) */}
            <motion.section
              variants={itemVariants}
              className="rounded-[2rem] border border-border bg-card p-5 shadow-xl flex flex-row items-center gap-4 relative overflow-hidden"
            >
              {/* Background Gradient for Aesthetics */}
              <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-blue-500/5 opacity-50 pointer-events-none" />

              <div className="relative z-10 flex-1 min-w-0 flex flex-col justify-center">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 mb-1">
                  <ShoppingBag size={14} className="text-emerald-400" />
                  Top Categories
                </h3>
                <span className="text-[10px] font-bold uppercase text-muted-foreground mb-2 block">{timeframe === "weekly" ? "Last 7 Days" : "This Month"}</span>
                <div className="flex flex-col gap-1.5">
                  {topCategories.slice(0, 3).map((cat, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full flex-shrink-0 shadow-[0_0_8px_rgba(0,0,0,0.5)]" style={{ backgroundColor: cat.color, boxShadow: `0 0 10px ${cat.color}40` }} />
                      <span className="text-[11px] text-muted-foreground truncate font-medium">{cat.name}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="w-[120px] h-[120px] relative flex-shrink-0 z-10">
                {topCategories.length === 0 ? (
                  <p className="text-muted-foreground text-[10px] italic absolute inset-0 flex items-center justify-center">No data</p>
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
                          <Cell key={`cell-${index}`} fill={entry.color} stroke="rgba(0,0,0,0.1)" strokeWidth={1} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{ backgroundColor: 'hsl(var(--popover))', borderColor: 'hsl(var(--border))', borderRadius: '8px', padding: '4px 8px' }}
                        itemStyle={{ color: 'hsl(var(--popover-foreground))', fontSize: '10px' }}
                        formatter={(value: number | string | undefined) => `₹${Number(value || 0).toLocaleString()}`}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </motion.section>

            {/* 3. Big Splurges (List) */}
            <motion.section
              variants={itemVariants}
              className="rounded-[2rem] border border-border bg-card p-5 shadow-xl flex flex-col relative overflow-hidden"
            >
              {/* Background Gradient for Aesthetics */}
              <div className="absolute inset-0 bg-gradient-to-br from-red-500/5 to-orange-500/5 opacity-50 pointer-events-none" />

              <div className="relative z-10 flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2">
                  <Zap size={14} className="text-yellow-500" />
                  Big Splurges
                </h3>
              </div>

              <div className="relative z-10 space-y-2 flex-1 overflow-y-auto custom-scrollbar pr-1">
                {splurges.length === 0 ? (
                  <div className="flex items-center justify-center h-full text-muted-foreground text-xs italic">No large purchases.</div>
                ) : (
                  splurges.map((tx, i) => (
                    <motion.div
                      whileHover={{ x: 2, backgroundColor: 'hsla(var(--foreground)/0.05)' }}
                      onClick={() => router.push(`/dashboard/transactions?openTx=${encodeURIComponent(tx.id)}`)}
                      key={tx.id}
                      className="flex items-center gap-3 p-2 rounded-lg border border-transparent transition-all cursor-pointer group bg-muted/30 hover:border-red-500/20"
                    >
                      <div className="h-6 w-6 rounded-md bg-red-500/20 flex items-center justify-center font-bold text-[10px] shrink-0 text-red-500 group-hover:bg-red-500 group-hover:text-white transition-colors">
                        {i + 1}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-bold text-foreground truncate group-hover:text-red-500 transition-colors">{tx.description || "Purchase"}</p>
                        <p className="text-[10px] text-muted-foreground truncate">{new Date(tx.transaction_date).toLocaleDateString()}</p>
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

          {/* Row 2: Full Width Spending Trends (Fixed Max/Min Colors) */}
          <motion.section
            variants={itemVariants}
            className="flex-1 min-h-[380px] rounded-[2rem] border border-border bg-card p-6 shadow-xl relative overflow-hidden flex flex-col"
          >
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-foreground flex items-center gap-2">
                  <Activity size={20} className="text-emerald-500" />
                  Spending Trends
                </h3>
                <p className="text-xs text-muted-foreground mt-1 ml-7">
                  {timeframe === "weekly" ? "Daily spending for last 7 days" : "Weekly spending for this month"}
                </p>
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
                    {/* Max Spending Gradient (Green) */}
                    <linearGradient id="maxGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#10B981" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#059669" stopOpacity={0.6} />
                    </linearGradient>
                    {/* Min Spending Gradient (Red) */}
                    <linearGradient id="minGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#EF4444" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#B91C1C" stopOpacity={0.6} />
                    </linearGradient>
                  </defs>
                  <Tooltip
                    cursor={{ fill: 'hsla(var(--foreground)/0.05)' }}
                    content={({ active, payload }) => {
                      if (active && payload && payload.length) {
                        return (
                          <div className="bg-popover border border-border p-3 rounded-xl shadow-xl backdrop-blur-md bg-opacity-90">
                            <p className="text-muted-foreground text-xs font-medium mb-1">{payload[0].payload.fullDate}</p>
                            <p className="text-foreground font-bold font-mono text-lg">₹{Number(payload[0].value).toLocaleString()}</p>
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
                    {trendData.map((entry, index) => {
                      const amounts = trendData.map(d => d.amount);
                      const maxVal = Math.max(...amounts);
                      const minVal = Math.min(...amounts);

                      let fillUrl = "url(#barGradient)";
                      if (entry.amount === maxVal && maxVal > 0) fillUrl = "url(#maxGradient)";
                      if (entry.amount === minVal) fillUrl = "url(#minGradient)";

                      return (
                        <Cell
                          key={`cell-${index}`}
                          fill={fillUrl}
                          className="hover:opacity-80 transition-opacity duration-300 cursor-pointer"
                          style={{ outline: 'none' }}
                        />
                      );
                    })}
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
