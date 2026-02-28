'use client';

import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { motion } from 'framer-motion';

interface Transaction {
  amount: number | string;
  category?: string;
}

const COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--destructive))',
  '#F59E0B', // Amber 500
  '#10B981', // Emerald 500
  '#8B5CF6', // Violet 500
  '#EC4899', // Pink 500
  '#6366F1', // Indigo 500
  '#14B8A6', // Teal 500
];

export function CategoryDistribution({ transactions }: { transactions: Transaction[] }) {
  const data = useMemo(() => {
    const map = new Map<string, number>();
    transactions.forEach(tx => {
      const amount = Number(tx.amount);
      if (amount < 0) {
        const cat = tx.category || 'Uncategorized';
        map.set(cat, (map.get(cat) || 0) + Math.abs(amount));
      }
    });

    const sorted = Array.from(map.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 6); // Top 6 categories

    // Add 'Other' if needed
    // ... logic for 'Other' can be added here if desired

    return sorted;
  }, [transactions]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay: 0.1 }}
      className="relative flex h-full min-h-0 flex-col overflow-hidden rounded-[2.5rem] border border-border bg-card p-6 shadow-xl"
    >
      <div className="absolute top-0 right-0 p-4 opacity-5 pointer-events-none">
        <div className="h-32 w-32 rounded-full bg-gradient-to-br from-primary to-transparent blur-3xl" />
      </div>

      <div className="relative z-10 mb-3">
        <h3 className="text-lg font-black text-foreground">Where it goes</h3>
        <p className="text-sm font-medium text-muted-foreground">Top spending categories.</p>
      </div>

      <div className="relative z-10 min-h-0 flex-1 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={80}
              paddingAngle={5}
              dataKey="value"
              nameKey="name"
              cornerRadius={8}
              stroke="none"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} strokeWidth={0} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value: number | undefined) => `₹${(Number(value) || 0).toLocaleString()}`}
              contentStyle={{
                backgroundColor: 'hsl(var(--card))',
                borderColor: 'hsl(var(--border))',
                borderRadius: '12px',
                boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
              }}
              itemStyle={{ color: 'hsl(var(--foreground))', fontWeight: 600 }}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
