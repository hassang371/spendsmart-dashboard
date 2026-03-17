import { useMemo, useSyncExternalStore } from 'react';
import { motion } from 'framer-motion';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { type Transaction } from '../../../../lib/api/client';
import { RefreshCw, CreditCard } from 'lucide-react';

interface SubscriptionRadarProps {
  transactions: Transaction[];
  isExpanded?: boolean;
}

const SUBSCRIPTION_KEYWORDS = [
  'netflix', 'spotify', 'apple', 'amazon prime', 'hulu', 'disney',
  'aws', 'adobe', 'vercel', 'github', 'zoom', 'slack', 'notion',
  'rent', 'electricity', 'water bill', 'internet', 'broadband', 'gym',
  'cult.fit', 'swiggy one', 'zomato gold'
];

export function SubscriptionRadar({ transactions, isExpanded = false }: SubscriptionRadarProps) {
  // Guard window.innerWidth for SSR safety using useSyncExternalStore.
  // Server snapshot returns false (desktop default) — no window access on server.
  // Refs: docs/bugs/BUG-010-subscriptionradar-window-ssr-crash.md
  const isSmall = useSyncExternalStore(
    (cb) => {
      window.addEventListener('resize', cb);
      return () => window.removeEventListener('resize', cb);
    },
    () => window.innerWidth < 640,
    () => false, // server snapshot: default to desktop
  );

  const { recurring, discretionary, recurringList } = useMemo(() => {
    let rec = 0;
    let disc = 0;
    const recList: { name: string; amount: number; date: string; category: string }[] = [];

    // Simple heuristic to mock subscription detection pending backend support
    transactions.forEach((tx) => {
      const amount = Number(tx.amount);
      if (amount >= 0) return; // Only expenses

      const absAmount = Math.abs(amount);
      const desc = tx.description.toLowerCase();

      const isRecurring = SUBSCRIPTION_KEYWORDS.some(k => desc.includes(k));

      if (isRecurring) {
        rec += absAmount;
        // Group by name naive assumption for this month's view
        const existing = recList.find(r => desc.includes(r.name.toLowerCase()));
        if (!existing) {
          recList.push({
            name: tx.description,
            amount: absAmount,
            date: new Date(tx.transaction_date).toLocaleDateString('en-US', { day: 'numeric', month: 'short' }),
            category: tx.category || 'Subscription'
          });
        }
      } else {
        disc += absAmount;
      }
    });

    return {
      recurring: rec,
      discretionary: disc,
      recurringList: recList.sort((a, b) => b.amount - a.amount)
    };
  }, [transactions]);

  const total = recurring + discretionary;
  const recurringPercent = total > 0 ? ((recurring / total) * 100).toFixed(1) : '0';

  const chartData = [
    { name: 'Recurring (Subscriptions & Bills)', value: recurring, color: '#ec4899' },
    { name: 'Discretionary', value: discretionary, color: 'hsl(var(--muted))' }
  ];

  if (transactions.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        No transaction data to analyze subscriptions.
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className={`relative flex h-full w-full flex-col min-h-0 ${isExpanded ? 'p-4' : ''}`}
    >
      {/* Metrics Header */}
      <div className="flex w-full items-center justify-between mb-4 px-4 pt-2">
         <div>
           <p className="text-sm font-medium text-muted-foreground">Fixed Cash Outflow</p>
           <div className="flex items-baseline gap-2">
              <h3 className="text-2xl lg:text-3xl font-black text-foreground">
                ₹{Math.round(recurring).toLocaleString('en-IN')}
              </h3>
              <span className="text-sm font-bold text-pink-500 bg-pink-500/10 px-2 py-0.5 rounded-full">
                {recurringPercent}% of expenses
              </span>
           </div>
         </div>
         {!isExpanded && (
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-card border border-border shadow-sm">
                <RefreshCw className="h-5 w-5 text-pink-500" />
            </div>
         )}
      </div>

      {isExpanded ? (
        // Expanded View: Table
        <div className="flex-1 w-full min-h-0 overflow-hidden mt-4 flex flex-col md:flex-row gap-8">
           <div className="w-full md:w-[calc(33.333%-1rem)] flex flex-col items-center justify-center border border-border rounded-3xl bg-card/30 p-8 shadow-inner min-w-0 min-h-[250px]">
             <div className="h-48 w-48 relative">
               <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={chartData}
                      innerRadius={60}
                      outerRadius={80}
                      paddingAngle={5}
                      dataKey="value"
                      stroke="none"
                      cornerRadius={8}
                    >
                      {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      formatter={(value: any) => `₹${Number(value).toLocaleString('en-IN')}`}
                      contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '12px' }}
                      itemStyle={{ color: 'hsl(var(--foreground))', fontWeight: 600 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                   <span className="text-2xl font-black text-foreground">{recurringPercent}%</span>
                   <span className="text-xs text-muted-foreground font-medium">Fixed</span>
                </div>
             </div>
             <p className="text-center text-sm text-muted-foreground mt-4 max-w-[200px]">
               Visual representation of your fixed recurring obligations vs discretionary spending.
             </p>
           </div>

           <div className="w-full md:w-[calc(66.666%-1rem)] flex flex-col bg-card/40 border border-border rounded-3xl overflow-hidden shadow-inner min-w-0 min-h-[250px]">
              <div className="border-b border-border bg-muted/20 px-6 py-4">
                <h4 className="font-bold text-foreground flex items-center gap-2">
                  <CreditCard className="w-4 h-4 text-muted-foreground" />
                  Identified Subscriptions
                </h4>
              </div>
              <div className="flex-1 overflow-y-auto no-scrollbar p-6">
                <div className="flex flex-col gap-4">
                  {recurringList.map((sub, i) => (
                    <div key={i} className="flex items-center justify-between p-4 rounded-2xl bg-background border border-border/50 hover:border-pink-500/30 transition-colors group">
                       <div className="flex items-center gap-4 min-w-0 flex-1">
                          <div className="flex h-10 w-10 items-center justify-center rounded-xl shrink-0 bg-muted/50 text-foreground font-bold group-hover:bg-pink-500/10 group-hover:text-pink-500 transition-colors">
                            {sub.name.charAt(0).toUpperCase()}
                          </div>
                          <div className="min-w-0 flex-1">
                            <p className="font-bold text-foreground text-sm truncate">{sub.name}</p>
                            <p className="text-xs text-muted-foreground font-medium truncate">{sub.category} • Last charged {sub.date}</p>
                          </div>
                       </div>
                       <div className="text-right shrink-0 ml-4">
                          <p className="font-bold text-foreground text-sm">₹{sub.amount.toLocaleString('en-IN')}</p>
                          <p className="text-xs text-muted-foreground font-medium">/ month</p>
                       </div>
                    </div>
                  ))}
                  {recurringList.length === 0 && (
                    <div className="text-center text-muted-foreground py-8">
                      No recurring subscriptions detected in this period.
                    </div>
                  )}
                </div>
              </div>
           </div>
        </div>
      ) : (
        // Compact View: Horizontal Radial/Bar
        <div className="flex-1 w-full min-h-[200px] flex items-center justify-center px-4 pb-4 mt-2">
           <ResponsiveContainer width="100%" height={200}>
             <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="100%"
                startAngle={180}
                endAngle={0}
                innerRadius={isSmall ? 90 : 110}
                outerRadius={isSmall ? 120 : 140}
                paddingAngle={4}
                dataKey="value"
                stroke="none"
                cornerRadius={8}
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={(value: any) => `₹${Number(value).toLocaleString('en-IN')}`}
                contentStyle={{ backgroundColor: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', borderRadius: '12px' }}
                itemStyle={{ color: 'hsl(var(--foreground))', fontWeight: 600 }}
              />
            </PieChart>
           </ResponsiveContainer>
        </div>
      )}
    </motion.div>
  );
}
