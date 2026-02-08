
"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight, TrendingUp } from "lucide-react";

interface Transaction {
    amount: number | string;
    transaction_date: string;
    type?: "credit" | "debit"; // Optional if implied by amount sign
}

interface MonthlyComparisonProps {
    transactions: Transaction[];
}

export function MonthlyComparison({ transactions }: MonthlyComparisonProps) {
    const stats = useMemo(() => {
        const now = new Date();
        const currentMonth = now.getMonth();
        const currentYear = now.getFullYear();

        // Calculate Previous Month
        const prevDate = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        const prevMonth = prevDate.getMonth();
        const prevYear = prevDate.getFullYear();

        let currentMonthSpend = 0;
        let prevMonthSpend = 0;

        transactions.forEach(tx => {
            const amount = Number(tx.amount);
            if (amount >= 0) return; // Ignore income

            const date = new Date(tx.transaction_date);
            const month = date.getMonth();
            const year = date.getFullYear();

            if (month === currentMonth && year === currentYear) {
                currentMonthSpend += Math.abs(amount);
            } else if (month === prevMonth && year === prevYear) {
                prevMonthSpend += Math.abs(amount);
            }
        });

        const percentChange = prevMonthSpend === 0
            ? 100
            : ((currentMonthSpend - prevMonthSpend) / prevMonthSpend) * 100;

        return { currentMonthSpend, prevMonthSpend, percentChange };
    }, [transactions]);

    const isSpendUp = stats.percentChange > 0;

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-[2rem] border border-border bg-card p-6 shadow-xl"
        >
            <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent pointer-events-none" />

            <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
                <TrendingUp className="h-40 w-40 text-primary rotate-12" />
            </div>

            <div className="relative z-10">
                <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Monthly Spend</h3>
                <div className="mt-2 flex items-baseline gap-2">
                    <h2 className="text-5xl font-black text-foreground tracking-tighter">
                        ₹{stats.currentMonthSpend.toLocaleString('en-IN')}
                    </h2>
                </div>

                <div className={`mt-4 inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm font-bold backdrop-blur-md shadow-sm ${isSpendUp
                    ? "border-red-500/20 bg-red-500/10 text-red-500"
                    : "border-emerald-500/20 bg-emerald-500/10 text-emerald-500"
                    }`}>
                    {isSpendUp ? <ArrowUpRight className="h-4 w-4" /> : <ArrowDownRight className="h-4 w-4" />}
                    {Math.abs(stats.percentChange).toFixed(1)}% vs Last Month
                </div>

                <p className="mt-4 text-xs font-medium text-muted-foreground">
                    You spent <span className="text-foreground font-bold">₹{stats.prevMonthSpend.toLocaleString('en-IN')}</span> last month.
                </p>
            </div>
        </motion.div>
    );
}
