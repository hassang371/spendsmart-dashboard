
"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import { Store, ShoppingBag, Star } from "lucide-react";

interface Transaction {
    amount: number | string;
    merchant_name?: string;
    description?: string;
}

export function MerchantLeaderboard({ transactions }: { transactions: Transaction[] }) {
    const data = useMemo(() => {
        const map = new Map<string, { amount: number; count: number }>();
        transactions.forEach(tx => {
            const amount = Number(tx.amount);
            if (amount < 0) {
                // Simple heuristic: use merchant_name if available, else description
                // Clean up common prefixes/suffixes if needed
                const rawName = tx.merchant_name || tx.description || "Unknown";
                const name = rawName.split('*')[0].trim(); // basic cleanup

                const current = map.get(name) || { amount: 0, count: 0 };
                map.set(name, { amount: current.amount + Math.abs(amount), count: current.count + 1 });
            }
        });

        return Array.from(map.entries())
            .map(([name, stats]) => ({ name, ...stats }))
            .sort((a, b) => b.amount - a.amount)
            .slice(0, 5);
    }, [transactions]);

    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-[2.5rem] border border-border bg-card p-6 shadow-xl"
        >
            <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
                <div className="h-40 w-40 rounded-full bg-gradient-to-br from-amber-500 to-transparent blur-3xl opacity-50" />
            </div>

            <div className="relative z-10 mb-4 flex items-center justify-between">
                <div>
                    <h3 className="text-lg font-black text-foreground">Top Merchants</h3>
                    <p className="text-sm font-medium text-muted-foreground">Your most visited spots.</p>
                </div>
                <div className="rounded-2xl bg-primary/10 p-3 shadow-inner">
                    <Store className="h-6 w-6 text-primary" />
                </div>
            </div>

            <div className="relative z-10 min-h-0 flex-1 space-y-3 overflow-y-auto pr-1 custom-scrollbar">
                {data.map((merchant, index) => (
                    <motion.div
                        key={merchant.name}
                        initial={{ opacity: 0, x: -20 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.3 + index * 0.1 }}
                        className="group flex items-center justify-between rounded-3xl border border-transparent bg-muted/30 p-4 transition-all hover:border-primary/20 hover:bg-muted/50 hover:shadow-lg"
                    >
                        <div className="flex items-center gap-4">
                            <div className={`flex h-12 w-12 items-center justify-center rounded-2xl font-black shadow-sm transition-transform group-hover:scale-110 ${index === 0 ? "bg-amber-500/20 text-amber-500 ring-2 ring-amber-500/10" :
                                    index === 1 ? "bg-zinc-400/20 text-zinc-400" :
                                        index === 2 ? "bg-orange-700/20 text-orange-700" :
                                            "bg-muted text-muted-foreground"
                                }`}>
                                {index < 3 ? <Star className="h-5 w-5 fill-current" /> : index + 1}
                            </div>
                            <div className="flex flex-col">
                                <h4 className="font-bold text-foreground text-base tracking-tight line-clamp-1 group-hover:text-primary transition-colors">
                                    {merchant.name}
                                </h4>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] uppercase font-bold text-muted-foreground bg-muted-foreground/10 px-2 py-0.5 rounded-full">
                                        {merchant.count} visits
                                    </span>
                                </div>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="font-mono text-lg font-black text-foreground tracking-tight">
                                ₹{merchant.amount.toLocaleString('en-IN')}
                            </p>
                        </div>
                    </motion.div>
                ))}
                {data.length === 0 && (
                    <div className="flex h-full flex-col items-center justify-center py-12 text-center text-muted-foreground">
                        <ShoppingBag className="h-12 w-12 opacity-20 mb-4" />
                        <p>No merchant data yet.</p>
                    </div>
                )}
            </div>
        </motion.div>
    );
}
