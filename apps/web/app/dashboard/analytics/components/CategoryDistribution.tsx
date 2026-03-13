'use client';

import { useMemo, useState } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Sector } from 'recharts';
import { motion } from 'framer-motion';

interface Transaction {
  amount: number | string;
  category?: string;
}

const COLORS = [
  'hsl(var(--primary))',
  'hsl(var(--destructive))',
  '#F59E0B',
  '#10B981',
  '#8B5CF6',
  '#EC4899',
  '#6366F1',
  '#14B8A6',
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const renderActiveShape = (props: any) => {
  const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill, payload } = props;

  return (
    <g>
      <text x={cx} y={cy} textAnchor="middle" fill={fill} className="text-sm md:text-xl font-black">
        {payload.name.length > 12 ? (
          <>
            <tspan x={cx} dy="-4">{payload.name.substring(0, 12)}</tspan>
            <tspan x={cx} dy="20">{payload.name.substring(12, 22) + (payload.name.length > 22 ? '...' : '')}</tspan>
          </>
        ) : (
          <tspan x={cx} dy={8}>{payload.name}</tspan>
        )}
      </text>
      <Sector
        cx={cx}
        cy={cy}
        innerRadius={innerRadius}
        outerRadius={outerRadius + 8}
        startAngle={startAngle}
        endAngle={endAngle}
        fill={fill}
        cornerRadius={8}
      />
      <Sector
        cx={cx}
        cy={cy}
        startAngle={startAngle}
        endAngle={endAngle}
        innerRadius={outerRadius + 12}
        outerRadius={outerRadius + 15}
        fill={fill}
        cornerRadius={4}
      />
    </g>
  );
};

export function CategoryDistribution({ transactions, isExpanded = false }: { transactions: Transaction[], isExpanded?: boolean }) {
  const [activeIndex, setActiveIndex] = useState(-1);

  const [prevIsExpanded, setPrevIsExpanded] = useState(isExpanded);

  if (isExpanded !== prevIsExpanded) {
    setPrevIsExpanded(isExpanded);
    if (!isExpanded) {
      setActiveIndex(-1);
    }
  }

  const { data, totalSpend } = useMemo(() => {
    const map = new Map<string, number>();
    let total = 0;
    transactions.forEach(tx => {
      const amount = Number(tx.amount);
      if (amount < 0) {
        const absAmount = Math.abs(amount);
        const cat = tx.category || 'Uncategorized';
        map.set(cat, (map.get(cat) || 0) + absAmount);
        total += absAmount;
      }
    });

    const sorted = Array.from(map.entries())
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, isExpanded ? 15 : 6);

    let otherSum = 0;
    if (!isExpanded && map.size > 6) {
      const others = Array.from(map.entries()).sort((a, b) => b[1] - a[1]).slice(6);
      otherSum = others.reduce((acc, curr) => acc + curr[1], 0);
      sorted.push({ name: 'Other', value: otherSum });
    }

    return { data: sorted, totalSpend: total };
  }, [transactions, isExpanded]);

  if (data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        No categorization data available.
      </div>
    );
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onPieEnter = (_: any, index: number) => {
    setActiveIndex(index);
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative flex h-full w-full flex-col min-h-0"
    >
      {!isExpanded && (
        <div className="relative z-10 mb-3 ml-4 mt-2">
          <p className="text-sm font-medium text-muted-foreground">Top spending categories.</p>
        </div>
      )}

      <div className={`relative z-10 w-full flex-1 min-h-0 mt-2 flex ${isExpanded ? 'flex-col md:flex-row gap-8 items-center' : 'flex-col'}`}>

        {/* Chart Area */}
        <div className={`${isExpanded ? 'w-full md:flex-1 h-[300px] md:h-full min-h-[300px] min-w-0' : 'w-full h-full min-h-[250px] min-w-0'}`}>
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                activeShape={renderActiveShape}
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={isExpanded ? 120 : 70}
                outerRadius={isExpanded ? 160 : 90}
                paddingAngle={5}
                dataKey="value"
                nameKey="name"
                cornerRadius={8}
                stroke="none"
                onClick={onPieEnter}
                onMouseEnter={onPieEnter}
                className="cursor-pointer focus:outline-none"
              >
                {data.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip
                // eslint-disable-next-line @typescript-eslint/no-explicit-any
                formatter={(value: any) => `₹${Number(value).toLocaleString('en-IN')}`}
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

        {/* Legend Area (Expanded Only) */}
        {isExpanded && (
          <div className="w-full md:flex-1 flex flex-col gap-3 overflow-y-auto max-h-full pr-4 custom-scrollbar min-w-0">
            <h4 className="text-xl font-bold mb-2">Category Breakdown</h4>
            {data.map((item, index) => {
              return (
                <div
                  key={index}
                  onMouseEnter={() => setActiveIndex(index)}
                  className={`flex items-center justify-between p-4 rounded-2xl border transition-all cursor-pointer ${activeIndex === index
                      ? 'border-primary/50 bg-primary/5 shadow-md scale-[1.02]'
                      : 'border-border/50 hover:border-primary/20 hover:bg-muted/50'
                    }`}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div
                      className="w-4 h-4 rounded-full shadow-sm shrink-0"
                      style={{ backgroundColor: COLORS[index % COLORS.length] }}
                    />
                    <div className="flex flex-col min-w-0 flex-1">
                      <span className="font-semibold text-foreground truncate">{item.name}</span>
                      <span className="text-xs text-muted-foreground whitespace-nowrap">
                        {((item.value / totalSpend) * 100).toFixed(1)}% of total
                      </span>
                    </div>
                  </div>
                  <span className="font-black tracking-tight shrink-0 ml-3">
                    ₹{item.value.toLocaleString('en-IN')}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </motion.div>
  );
}
