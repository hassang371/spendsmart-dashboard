'use client';

import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Shield, Loader2, Activity, AlertCircle, RefreshCw } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { apiSafeToSpend, type SafeToSpendResponse } from '../../lib/api/client';
import { getBrowserSupabaseClient } from '../../lib/supabase/client';

export default function SafeToSpendCard() {
  const [data, setData] = useState<SafeToSpendResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const supabase = getBrowserSupabaseClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token;

      const result = await apiSafeToSpend(token);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="group relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-emerald-500 to-teal-600 p-6 text-white shadow-xl">
        <div className="flex items-center gap-3">
          <Loader2 className="h-6 w-6 animate-spin text-white/70" />
          <span className="text-sm font-medium text-white/70">Calculating safe-to-spend...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="group relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-red-500 to-orange-600 p-6 text-white shadow-xl">
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            <span className="text-sm font-bold">Unable to load data</span>
          </div>
          <button
            onClick={fetchData}
            className="flex w-fit items-center gap-2 rounded-xl bg-white/20 px-3 py-1.5 text-xs font-bold transition-colors hover:bg-white/30"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!data) return null;

  return (
    <motion.div
      whileHover={{ scale: 1.015 }}
      className="group relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-emerald-500 to-teal-600 p-6 text-white shadow-xl shadow-emerald-900/20 transition-shadow duration-300 hover:shadow-2xl"
    >
      {/* Background decoration */}
      <div className="pointer-events-none absolute right-0 top-0 p-6 opacity-10 transition-opacity duration-500 group-hover:opacity-20">
        <Shield className="h-32 w-32" />
      </div>

      <div className="relative z-10 flex flex-col justify-between h-full">
        <div>
          <div className="mb-1 flex items-center gap-2">
            <div className="rounded-full bg-white/20 p-1.5 backdrop-blur-sm">
              <Shield className="h-3.5 w-3.5 text-white" />
            </div>
            <span className="text-[10px] font-bold uppercase tracking-wider text-white/90">
              Safe to Spend
            </span>
            <span className="ml-auto text-[10px] font-medium text-white/60">
              {data.horizon_days}-day horizon
            </span>
          </div>

          <h2 className="mt-2 text-4xl font-mono font-black tracking-tighter">
            ₹{data.safe_amount.toLocaleString('en-IN')}
          </h2>

          <div className="mt-3 flex items-center gap-3">
            <div className="inline-flex items-center gap-1.5 rounded-xl border border-white/20 bg-white/10 px-2.5 py-1 text-[10px] font-bold backdrop-blur-sm">
              <Activity className="h-3 w-3" />
              <span>{(data.confidence * 100).toFixed(0)}% confidence</span>
            </div>
            <span className="text-[10px] font-medium text-white/60 capitalize">
              Model: {data.model.replace(/_/g, ' ')}
            </span>
          </div>
        </div>

        {/* Forecast Chart (Mini) */}
        {data.forecast_breakdown && data.forecast_breakdown.length > 0 && (
          <div className="mt-6 h-24 w-full opacity-80 transition-opacity hover:opacity-100">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.forecast_breakdown}>
                <defs>
                  <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ffffff" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#ffffff" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" hide />
                <YAxis hide />
                <Tooltip
                  cursor={{ stroke: 'rgba(255,255,255,0.2)' }}
                  contentStyle={{
                    backgroundColor: 'rgba(0,0,0,0.8)',
                    border: 'none',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#fff',
                  }}
                  itemStyle={{ color: '#fff' }}
                  labelStyle={{ color: '#ccc' }}
                />
                <Area
                  type="monotone"
                  dataKey="p50"
                  stroke="#ffffff"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#chartGradient)"
                />
                {/* Optional uncertainty bands p10/p90 could go here */}
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Bottom accent line */}
      <div className="absolute inset-x-0 bottom-0 h-1 bg-white/20" />
    </motion.div>
  );
}
