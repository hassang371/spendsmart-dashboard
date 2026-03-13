'use client';

import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Store, ShoppingBag, Star } from 'lucide-react';

interface Transaction {
  amount: number | string;
  merchant_name?: string;
  description?: string;
}

export function MerchantLeaderboard({ transactions, isExpanded = false }: { transactions: Transaction[], isExpanded?: boolean }) {
  const { data, maxAmount, totalSpend } = useMemo(() => {
    const map = new Map<string, { amount: number; count: number }>();
    let total = 0;

    transactions.forEach(tx => {
      const amount = Number(tx.amount);
      if (amount < 0) {
        const rawName = tx.merchant_name || tx.description || 'Unknown';
        const name = rawName.split('*')[0].trim();
        const absAmount = Math.abs(amount);

        const current = map.get(name) || { amount: 0, count: 0 };
        map.set(name, { amount: current.amount + absAmount, count: current.count + 1 });
        total += absAmount;
      }
    });

    const sorted = Array.from(map.entries())
      .map(([name, stats]) => ({ name, ...stats }))
      .sort((a, b) => b.amount - a.amount)
      .slice(0, isExpanded ? 15 : 5);

    const max = sorted.length > 0 ? sorted[0].amount : 0;

    return { data: sorted, maxAmount: max, totalSpend: total };
  }, [transactions, isExpanded]);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative flex h-full w-full flex-col min-h-0"
    >
      <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
        <div className="h-40 w-40 rounded-full bg-gradient-to-br from-amber-500 to-transparent blur-3xl" />
      </div>

      {!isExpanded && (
        <div className="relative z-10 mb-4 ml-4 mt-2 flex items-center justify-between pr-4">
          <div>
            <h3 className="text-lg font-black text-foreground">Top Merchants</h3>
            <p className="text-sm font-medium text-muted-foreground">Your most visited spots.</p>
          </div>
          <div className="rounded-2xl bg-amber-500/10 p-3 shadow-inner hidden sm:block">
            <Store className="h-6 w-6 text-amber-500" />
          </div>
        </div>
      )}

      {isExpanded && (
         <div className="relative z-10 mb-6 flex flex-col gap-1">
             <h3 className="text-xl font-black text-foreground">Merchant Leaderboard</h3>
             <p className="text-sm text-muted-foreground">Detailed breakdown of your spending by merchant.</p>
         </div>
      )}

      {data.length === 0 ? (
        <div className="flex h-full flex-col items-center justify-center py-12 text-center text-muted-foreground">
          <ShoppingBag className="h-12 w-12 opacity-20 mb-4" />
          <p>No merchant data yet.</p>
        </div>
      ) : (
        <div className="relative z-10 min-h-0 flex-1 space-y-3 overflow-y-auto pr-2 custom-scrollbar">
          {isExpanded ? (
            // Expanded Rich Data Table View
            <div className="w-full text-sm">
                <div className="grid grid-cols-12 gap-4 pb-3 border-b border-border/50 text-muted-foreground font-semibold px-4">
                    <div className="col-span-1 text-center">#</div>
                    <div className="col-span-5">Merchant</div>
                    <div className="col-span-3">Spend Volume</div>
                    <div className="col-span-3 text-right">Total Amount</div>
                </div>
                <div className="flex flex-col gap-2 mt-3">
                    {data.map((merchant, index) => (
                        <div key={merchant.name} className="grid grid-cols-12 gap-4 py-3 px-4 items-center rounded-xl hover:bg-muted/30 transition-colors">
                            <div className="col-span-1 text-center font-bold text-muted-foreground">
                                {index + 1}
                            </div>
                            <div className="col-span-5 flex flex-col">
                                <span className="font-bold text-foreground text-base truncate">{merchant.name}</span>
                                <span className="text-xs text-muted-foreground">{merchant.count} transactions</span>
                            </div>
                            <div className="col-span-3 flex flex-col justify-center gap-1.5">
                                <div className="w-full bg-muted rounded-full h-2 overflow-hidden flex">
                                    <div
                                        className="bg-amber-500 rounded-full h-full"
                                        style={{ width: `${(merchant.amount / maxAmount) * 100}%` }}
                                    />
                                </div>
                                <span className="text-[10px] text-muted-foreground font-mono">
                                    {((merchant.amount / totalSpend) * 100).toFixed(1)}% of total
                                </span>
                            </div>
                            <div className="col-span-3 text-right font-black text-foreground">
                                ₹{merchant.amount.toLocaleString('en-IN')}
                            </div>
                        </div>
                    ))}
                </div>
            </div>
          ) : (
            // Compact List View
            data.map((merchant, index) => (
              <div
                key={merchant.name}
                className="group flex items-center justify-between rounded-3xl border border-transparent bg-muted/20 p-4 transition-all hover:border-border hover:bg-muted/40"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-2xl font-black shadow-sm transition-transform group-hover:scale-105 ${
                      index === 0
                        ? 'bg-amber-500/20 text-amber-500 ring-2 ring-amber-500/20'
                        : index === 1
                          ? 'bg-zinc-400/20 text-zinc-400'
                          : index === 2
                            ? 'bg-orange-700/20 text-orange-700'
                            : 'bg-muted/50 text-muted-foreground'
                    }`}
                  >
                    {index < 3 ? <Star className="h-5 w-5 fill-current" /> : index + 1}
                  </div>
                  <div className="flex flex-col">
                    <h4 className="font-bold text-foreground text-base tracking-tight line-clamp-1 group-hover:text-primary transition-colors">
                      {merchant.name}
                    </h4>
                    <span className="text-[10px] uppercase font-bold text-muted-foreground bg-foreground/5 w-fit px-2 py-0.5 rounded-full mt-1">
                      {merchant.count} visits
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-mono text-lg font-black text-foreground tracking-tight">
                    ₹{merchant.amount.toLocaleString('en-IN')}
                  </p>
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </motion.div>
  );
}
