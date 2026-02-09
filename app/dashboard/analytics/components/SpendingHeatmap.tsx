
"use client";

import { useMemo } from "react";
import { Bar, BarChart, ResponsiveContainer, XAxis, Tooltip, Cell } from "recharts";
import { motion } from "framer-motion";

interface Transaction {
    amount: number | string;
    transaction_date: string;
}

export function SpendingHeatmap({ transactions }: { transactions: Transaction[] }) {
    const data = useMemo(() => {
        const days = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
        const counts = new Array(7).fill(0);

        transactions.forEach(tx => {
            const amount = Number(tx.amount);
            if (amount >= 0) return; // Ignore income
            const date = new Date(tx.transaction_date);
            if (isNaN(date.getTime())) return;
            const day = date.getDay();
            counts[day] += Math.abs(amount);
        });

        return days.map((day, index) => ({
            day,
            amount: counts[index],
        }));
    }, [transactions]);

    const maxAmount = Math.max(...data.map(d => d.amount));

    return (
        <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-[2.5rem] border border-border bg-card p-6 shadow-xl"
        >
            <div className="absolute -top-10 -right-10 p-4 opacity-5 pointer-events-none">
                <div className="h-40 w-40 rounded-full bg-gradient-to-br from-blue-500 to-transparent blur-3xl opacity-50" />
            </div>

            <div className="relative z-10 mb-3">
                <h3 className="text-lg font-black text-foreground">Weekly Rhythm</h3>
                <p className="text-sm font-medium text-muted-foreground">Which days do you spend the most?</p>
            </div>

            <div className="relative z-10 min-h-0 flex-1 w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data}>
                        <defs>
                            <linearGradient id="heatmapBarGradient" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={1} />
                                <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0.6} />
                            </linearGradient>
                            <linearGradient id="heatmapBarGradientInactive" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.3} />
                                <stop offset="100%" stopColor="hsl(var(--muted-foreground))" stopOpacity={0.1} />
                            </linearGradient>
                        </defs>
                        <XAxis
                            dataKey="day"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12, fontWeight: 700 }}
                            dy={10}
                        />
                        <Tooltip
                            cursor={{ fill: 'transparent' }}
                            content={({ active, payload }) => {
                                if (active && payload && payload.length) {
                                    return (
                                        <div className="rounded-xl border border-white/10 bg-black/80 p-3 shadow-xl backdrop-blur-md">
                                            <p className="text-xs font-bold text-gray-400 mb-1">{payload[0].payload.day}</p>
                                            <p className="text-xl font-black text-white">
                                                ₹{Number(payload[0].value).toLocaleString('en-IN')}
                                            </p>
                                        </div>
                                    );
                                }
                                return null;
                            }}
                        />
                        <Bar dataKey="amount" radius={[12, 12, 12, 12]}>
                            {data.map((entry, index) => (
                                <Cell
                                    key={`cell-${index}`}
                                    fill={entry.amount === maxAmount ? "url(#heatmapBarGradient)" : "url(#heatmapBarGradientInactive)"}
                                    className="transition-all duration-300 hover:opacity-80"
                                />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </motion.div>
    );
}
