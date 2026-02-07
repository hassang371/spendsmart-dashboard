"use client";
import { useEffect, useState } from "react";
import { ArrowUpRight, ArrowDownLeft, TrendingUp, CreditCard, Loader2 } from "lucide-react";
import { supabase } from "../../lib/supabase";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";

// Types
type Transaction = {
    id: string;
    description: string;
    amount: number;
    transaction_date: string;
    category: string;
    type?: string;
};

export default function DashboardPage() {
    const router = useRouter();
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [stats, setStats] = useState({
        netWorth: 0,
        income: 0,
        expenses: 0
    });

    useEffect(() => {
        async function fetchData() {
            const {
                data: { user },
                error: userError,
            } = await supabase.auth.getUser();

            if (userError || !user) {
                router.replace("/login");
                return;
            }

            const { data, error } = await supabase
                .from("transactions")
                .select("*")
                .eq("user_id", user.id)
                .order("transaction_date", { ascending: false })
                .limit(20);

            if (error) {
                console.error("Error fetching transactions:", error);
                setError("Unable to load transactions right now.");
            } else if (data) {
                setTransactions(data);

                let net = 0;
                let inc = 0;
                let exp = 0;

                data.forEach((txn) => {
                    const amt = Number(txn.amount);
                    net += amt;
                    if (amt > 0) inc += amt;
                    else exp += Math.abs(amt);
                });

                setStats({ netWorth: net, income: inc, expenses: exp });
            }
            setLoading(false);
        }

        fetchData();
    }, [router]);

    if (loading) {
        return (
            <div className="flex h-[50vh] items-center justify-center">
                <Loader2 className="animate-spin text-primary w-12 h-12" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-2xl border border-red-500/40 bg-red-500/10 p-6 text-red-100">
                {error}
            </div>
        );
    }

    const containerVariants = {
        hidden: { opacity: 0 },
        visible: {
            opacity: 1,
            transition: {
                staggerChildren: 0.1
            }
        }
    };

    const itemVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: { opacity: 1, y: 0 }
    };

    return (
        <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="space-y-6"
        >
            {/* Top Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                {/* Main Balance Card */}
                <motion.div
                    variants={itemVariants}
                    className="md:col-span-2 bg-gradient-to-br from-secondary to-gray-900 rounded-3xl p-8 border border-white/5 relative overflow-hidden group shadow-slush"
                >
                    <div className="absolute top-0 right-0 p-8 opacity-20 group-hover:opacity-40 transition-opacity">
                        <CreditCard size={120} />
                    </div>
                    <p className="text-gray-400 font-medium mb-2">Total Net Worth</p>
                    <h2 className="text-5xl font-mono font-bold mb-4 tracking-tighter text-white group-hover:scale-[1.02] transition-transform origin-left">
                        ${stats.netWorth.toFixed(2)}
                    </h2>
                    <div className="flex items-center gap-2 text-success bg-success/10 px-3 py-1 rounded-full w-fit">
                        <TrendingUp size={16} />
                        <span className="text-sm font-bold">+2.4% this month</span>
                    </div>
                </motion.div>

                {/* Income Card */}
                <motion.div
                    variants={itemVariants}
                    className="bg-[#10B981] text-black rounded-3xl p-6 flex flex-col justify-between hover:scale-[1.05] transition-transform shadow-slush-sm cursor-pointer"
                >
                    <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center mb-4">
                        <ArrowDownLeft size={20} />
                    </div>
                    <div>
                        <p className="text-black/60 font-medium text-sm">Income</p>
                        <h3 className="text-3xl font-bold mt-1 text-white shadow-sm font-mono">${stats.income.toFixed(2)}</h3>
                    </div>
                </motion.div>

                {/* Expense Card */}
                <motion.div
                    variants={itemVariants}
                    className="bg-[#EF4444] text-white rounded-3xl p-6 flex flex-col justify-between hover:scale-[1.05] transition-transform shadow-slush-sm cursor-pointer"
                >
                    <div className="w-10 h-10 bg-white/20 rounded-full flex items-center justify-center mb-4">
                        <ArrowUpRight size={20} />
                    </div>
                    <div>
                        <p className="text-white/80 font-medium text-sm">Expenses</p>
                        <h3 className="text-3xl font-bold mt-1 font-mono">${stats.expenses.toFixed(2)}</h3>
                    </div>
                </motion.div>
            </div>

            {/* Recent Activity & Charts */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Chart Placeholder */}
                <motion.div
                    variants={itemVariants}
                    className="md:col-span-2 bg-secondary rounded-3xl p-6 border border-white/5 shadow-md overflow-hidden relative"
                >
                    <div className="flex justify-between items-center mb-6">
                        <h3 className="font-bold text-lg text-white">Spending Trends</h3>
                        <select className="bg-background border border-white/10 rounded-lg px-3 py-1 text-sm text-gray-400">
                            <option>Last 30 Days</option>
                            <option>Last 3 Months</option>
                        </select>
                    </div>
                    <div className="h-64 flex items-end gap-2 px-4 pb-4 border-b border-l border-white/5">
                        {[40, 65, 30, 80, 55, 90, 45, 70, 60, 85].map((h, i) => (
                            <motion.div
                                initial={{ height: 0 }}
                                animate={{ height: `${h}% ` }}
                                transition={{ delay: 0.5 + i * 0.05, duration: 0.5 }}
                                key={i}
                                className="flex-1 bg-primary/20 hover:bg-primary/80 transition-colors rounded-t-sm relative group cursor-pointer"
                            ></motion.div>
                        ))}
                    </div>
                </motion.div>

                {/* Recent List */}
                <motion.div
                    variants={itemVariants}
                    className="bg-secondary rounded-3xl p-6 border border-white/5 overflow-hidden flex flex-col shadow-md"
                >
                    <h3 className="font-bold text-lg mb-4 text-white">Recent Transactions</h3>
                    <div className="flex-1 overflow-y-auto space-y-4 pr-2 max-h-[400px]">
                        {transactions.length === 0 ? (
                            <p className="text-gray-500 text-center py-10">No transactions found.</p>
                        ) : (
                            transactions.map((txn, i) => (
                                <motion.div
                                    initial={{ opacity: 0, x: 20 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: i * 0.05 }}
                                    key={txn.id}
                                    className="flex items-center justify-between p-3 hover:bg-white/5 rounded-xl transition-colors cursor-pointer group"
                                >
                                    <div className="flex items-center gap-3">
                                        <div className="w-10 h-10 bg-background rounded-full flex items-center justify-center text-lg border border-white/5 group-hover:border-white/20 transition-colors">
                                            {Number(txn.amount) > 0 ? "💰" : "💸"}
                                        </div>
                                        <div>
                                            <p className="font-bold text-sm text-white truncate max-w-[120px]">{txn.description}</p>
                                            <p className="text-xs text-gray-400">{new Date(txn.transaction_date).toLocaleDateString()}</p>
                                        </div>
                                    </div>
                                    <span className={`font-mono font-bold ${Number(txn.amount) > 0 ? 'text-success' : 'text-white'} `}>
                                        {Number(txn.amount) > 0 ? "+" : ""}{Number(txn.amount).toFixed(2)}
                                    </span>
                                </motion.div>
                            ))
                        )}
                    </div>
                    <motion.button
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        className="w-full mt-4 py-2 border border-white/10 rounded-xl text-sm font-bold hover:bg-white/5 transition-colors text-white"
                    >
                        View All
                    </motion.button>
                </motion.div>
            </div>
        </motion.div>
    );
}
