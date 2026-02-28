'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { motion, Variants, AnimatePresence } from 'framer-motion';
import {
  Brain,
  TrendingUp,
  Upload,
  FileText,
  Loader2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Zap,
  Sparkles,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, Legend } from 'recharts';

import {
  apiHealthCheck,
  apiForecastPredict,
  apiUploadTrainingData,
  type ForecastResponse,
  type HealthResponse,
  type TrainingUploadResponse,
} from '../../../lib/api/client';
import { getBrowserSupabaseClient } from '../../../lib/supabase/client';
import SafeToSpendCard from '../../../components/dashboard/SafeToSpendCard';
import TrainingJobCard from '../../../components/dashboard/TrainingJobCard';

// ── Animation Variants ──────────────────────────────────────────

const containerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.12 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: 'spring', stiffness: 260, damping: 22 },
  },
};

// ── Offline State Component ─────────────────────────────────────

function OfflineState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
      <div className="rounded-full bg-destructive/10 p-4">
        <AlertCircle className="h-8 w-8 text-destructive" />
      </div>
      <div>
        <p className="text-sm font-bold text-foreground">{message}</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Make sure the API gateway is running on port 8000
        </p>
      </div>
      <button
        onClick={onRetry}
        className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-border bg-muted px-4 py-2 text-xs font-bold text-foreground transition-colors duration-200 hover:bg-muted/80"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Retry Connection
      </button>
    </div>
  );
}

// ── Main Page ───────────────────────────────────────────────────

export default function AIInsightsPage() {
  // Gateway status
  const [gatewayOnline, setGatewayOnline] = useState<boolean | null>(null);
  const [healthData, setHealthData] = useState<HealthResponse | null>(null);
  const [checkingHealth, setCheckingHealth] = useState(true);

  // Safe-to-Spend state removed (moved to component)

  // Forecast
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forecastError, setForecastError] = useState<string | null>(null);

  // Training
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [trainingResult, setTrainingResult] = useState<TrainingUploadResponse | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [trainingPassword, setTrainingPassword] = useState('');
  const trainingFileRef = useRef<HTMLInputElement | null>(null);

  // File upload (Forecast)
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);

  // ── Health Check ────────────────────────────────────────────

  const checkGateway = useCallback(async () => {
    setCheckingHealth(true);
    try {
      const data = await apiHealthCheck();
      setHealthData(data);
      setGatewayOnline(true);
    } catch {
      setGatewayOnline(false);
      setHealthData(null);
    } finally {
      setCheckingHealth(false);
    }
  }, []);

  useEffect(() => {
    checkGateway();
  }, [checkGateway]);

  // Safe-to-Spend effect removed

  // ── Forecast Upload ─────────────────────────────────────────

  const handleForecastUpload = useCallback(async (file: File) => {
    setForecastLoading(true);
    setForecastError(null);
    setUploadedFileName(file.name);

    try {
      const supabase = getBrowserSupabaseClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token;

      const data = await apiForecastPredict(file, token);
      setForecast(data);
    } catch (err) {
      setForecastError(err instanceof Error ? err.message : 'Failed to generate forecast');
      setForecast(null);
    } finally {
      setForecastLoading(false);
    }
  }, []);

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleForecastUpload(file);
      // Reset for re-upload
      if (e.target) e.target.value = '';
    },
    [handleForecastUpload]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleForecastUpload(file);
    },
    [handleForecastUpload]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  // ── Training Upload Handler ─────────────────────────────────

  const handleTrainingUpload = useCallback(
    async (file: File) => {
      setTrainingLoading(true);
      setTrainingError(null);
      setTrainingResult(null);

      try {
        const supabase = getBrowserSupabaseClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        const token = session?.access_token;

        const data = await apiUploadTrainingData(file, trainingPassword || undefined, token);
        setTrainingResult(data);
      } catch (err) {
        setTrainingError(err instanceof Error ? err.message : 'Failed to trigger training job');
        setTimeout(() => setTrainingError(null), 5000);
      } finally {
        setTrainingLoading(false);
      }
    },
    [trainingPassword]
  );

  const handleTrainingFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleTrainingUpload(file);
      if (e.target) e.target.value = '';
    },
    [handleTrainingUpload]
  );

  // ── Render ──────────────────────────────────────────────────

  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-1 md:p-2"
    >
      {/* Header */}
      <motion.div variants={itemVariants} className="flex items-end justify-between">
        <div>
          <h1 className="flex items-center gap-3 text-3xl font-black tracking-tight text-foreground">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-500/20">
              <Brain className="h-5 w-5 text-white" />
            </div>
            AI Insights
          </h1>
          <p className="mt-1 text-sm font-medium text-muted-foreground">
            Powered by the SCALE Intelligence Engine
          </p>
        </div>

        {/* Gateway Status Badge */}
        <div
          className={`inline-flex items-center gap-2 rounded-2xl border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide backdrop-blur-md transition-colors duration-300 ${checkingHealth
              ? 'border-border bg-muted text-muted-foreground'
              : gatewayOnline
                ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-500'
                : 'border-destructive/20 bg-destructive/10 text-destructive'
            }`}
        >
          <div
            className={`h-1.5 w-1.5 rounded-full ${checkingHealth
                ? 'animate-pulse bg-muted-foreground'
                : gatewayOnline
                  ? 'bg-emerald-500 animate-pulse'
                  : 'bg-destructive'
              }`}
          />
          {checkingHealth ? 'Connecting...' : gatewayOnline ? 'Engine Online' : 'Engine Offline'}
        </div>
      </motion.div>

      {/* Row 1: Safe-to-Spend + Engine Info */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {/* Safe-to-Spend Card */}
        {/* Safe-to-Spend Card */}
        <div className="col-span-1 md:col-span-2">
          <SafeToSpendCard />
        </div>

        {/* Engine Status Card */}
        <motion.div
          variants={itemVariants}
          className="relative overflow-hidden rounded-[2rem] border border-border bg-card p-6 shadow-xl"
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-violet-500/5 to-indigo-500/5 opacity-50" />

          <div className="relative z-10">
            <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
              <Zap className="h-4 w-4 text-violet-500" />
              Engine Status
            </h3>

            {checkingHealth ? (
              <div className="mt-4 flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                <span className="text-xs text-muted-foreground">Connecting...</span>
              </div>
            ) : gatewayOnline && healthData ? (
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Gateway</span>
                  <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-500">
                    <CheckCircle2 className="h-3 w-3" />
                    Online
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">API</span>
                  <span className="text-xs font-mono font-bold text-foreground">
                    {healthData.services?.api || healthData.engines?.ingestion || 'unknown'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Redis</span>
                  <span className="text-xs font-mono font-bold text-foreground">
                    {healthData.services?.redis || 'unknown'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Celery</span>
                  <span className="text-xs font-mono font-bold text-foreground">
                    {healthData.services?.celery || 'unknown'}
                  </span>
                </div>
              </div>
            ) : (
              <OfflineState message="Cannot reach engine" onRetry={checkGateway} />
            )}
          </div>
        </motion.div>
      </div>

      {/* Row 2: Forecast Section */}
      <motion.div
        variants={itemVariants}
        className="relative flex min-h-[380px] flex-1 flex-col overflow-hidden rounded-[2rem] border border-border bg-card p-6 shadow-xl"
      >
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-blue-500/5 to-violet-500/5 opacity-50" />

        <div className="relative z-10 flex flex-col flex-1 min-h-0">
          {/* Section Header */}
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="flex items-center gap-2 text-xl font-bold text-foreground">
                <TrendingUp className="h-5 w-5 text-blue-500" />
                7-Day Spending Forecast
              </h3>
              <p className="ml-7 mt-1 text-xs text-muted-foreground">
                Upload a CSV of transactions to generate AI predictions
              </p>
            </div>

            {forecast && (
              <div className="flex items-center gap-1.5 rounded-full border border-violet-500/20 bg-violet-500/10 px-3 py-1.5">
                <Sparkles className="h-3 w-3 text-violet-400" />
                <span className="text-[10px] font-bold uppercase text-violet-400">
                  {forecast.model}
                </span>
              </div>
            )}
          </div>

          {/* Content: Upload or Chart */}
          {/* Content: Upload or Chart */}
          {forecastLoading ? (
            /* Loading State */
            <div className="flex flex-1 flex-col items-center justify-center gap-4">
              <div className="relative">
                <Loader2 className="h-12 w-12 animate-spin text-primary" />
                <div className="absolute inset-0 rounded-full bg-primary/10 animate-ping" />
              </div>
              <div className="text-center">
                <p className="text-sm font-bold text-foreground">Generating forecast...</p>
                <p className="mt-1 text-xs text-muted-foreground">Analyzing {uploadedFileName}</p>
              </div>
            </div>
          ) : forecastError ? (
            /* Error State */
            <div className="flex flex-1 flex-col items-center justify-center gap-4">
              <div className="rounded-full bg-destructive/10 p-4">
                <AlertCircle className="h-8 w-8 text-destructive" />
              </div>
              <div className="text-center">
                <p className="text-sm font-bold text-foreground">{forecastError}</p>
                <button
                  onClick={() => {
                    setForecast(null);
                    setForecastError(null);
                    setUploadedFileName(null);
                  }}
                  className="mt-3 cursor-pointer rounded-xl border border-border bg-muted px-4 py-2 text-xs font-bold text-foreground transition-colors hover:bg-muted/80"
                >
                  Try Again
                </button>
              </div>
            </div>
          ) : forecast ? (
            /* Forecast Chart */
            <div className="flex flex-1 flex-col min-h-0">
              {/* File indicator + re-upload */}
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2 rounded-xl border border-border bg-muted px-3 py-1.5">
                  <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground">
                    {uploadedFileName}
                  </span>
                </div>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="cursor-pointer text-xs font-bold text-primary transition-colors hover:text-primary/80"
                >
                  Upload different file
                </button>
              </div>

              {/* Chart */}
              <div className="flex-1 min-h-0 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={forecast.predictions}
                    margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient id="spendGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#EF4444" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="#B91C1C" stopOpacity={0.4} />
                      </linearGradient>
                      <linearGradient id="incomeGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#10B981" stopOpacity={0.85} />
                        <stop offset="100%" stopColor="#059669" stopOpacity={0.4} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="day_offset"
                      axisLine={false}
                      tickLine={false}
                      tick={{
                        fill: '#6B7280',
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                      tickFormatter={(v: number) => `Day ${v}`}
                      dy={10}
                    />
                    <YAxis
                      axisLine={false}
                      tickLine={false}
                      tick={{
                        fill: '#6B7280',
                        fontSize: 11,
                        fontWeight: 500,
                      }}
                      tickFormatter={(v: number) => `₹${v.toLocaleString()}`}
                      width={70}
                    />
                    <Tooltip
                      cursor={{ fill: 'hsla(var(--foreground)/0.05)' }}
                      content={({ active, payload }) => {
                        if (active && payload && payload.length) {
                          const entry = payload[0]?.payload;
                          return (
                            <div className="rounded-xl border border-border bg-popover p-3 shadow-xl backdrop-blur-md">
                              <p className="mb-1 text-xs font-medium text-muted-foreground">
                                Day {entry?.day_offset}
                              </p>
                              <p className="text-sm font-bold text-red-400">
                                Spend: ₹{Number(entry?.predicted_spend || 0).toLocaleString()}
                              </p>
                              <p className="text-sm font-bold text-emerald-400">
                                Income: ₹{Number(entry?.predicted_income || 0).toLocaleString()}
                              </p>
                              <p className="mt-1 text-xs font-mono font-bold text-foreground">
                                Net: ₹{Number(entry?.predicted_net || 0).toLocaleString()}
                              </p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Legend
                      verticalAlign="top"
                      align="right"
                      iconType="circle"
                      iconSize={8}
                      wrapperStyle={{ fontSize: '11px', fontWeight: 600, paddingBottom: '8px' }}
                    />
                    <Bar
                      dataKey="predicted_spend"
                      name="Predicted Spend"
                      fill="url(#spendGrad)"
                      radius={[6, 6, 0, 0]}
                      animationDuration={1200}
                    >
                      {forecast.predictions.map((_, i) => (
                        <Cell
                          key={`spend-${i}`}
                          fill="url(#spendGrad)"
                          className="cursor-pointer transition-opacity duration-300 hover:opacity-80"
                          style={{ outline: 'none' }}
                        />
                      ))}
                    </Bar>
                    <Bar
                      dataKey="predicted_income"
                      name="Predicted Income"
                      fill="url(#incomeGrad)"
                      radius={[6, 6, 0, 0]}
                      animationDuration={1200}
                    >
                      {forecast.predictions.map((_, i) => (
                        <Cell
                          key={`income-${i}`}
                          fill="url(#incomeGrad)"
                          className="cursor-pointer transition-opacity duration-300 hover:opacity-80"
                          style={{ outline: 'none' }}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Forecast summary */}
              <div className="mt-3 flex items-center gap-4 rounded-xl border border-border bg-muted/50 px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-red-500" />
                  <span className="text-[11px] font-bold text-muted-foreground">
                    Total Spend:{' '}
                    <span className="font-mono text-red-400">
                      ₹
                      {forecast.predictions
                        .reduce((s, p) => s + p.predicted_spend, 0)
                        .toLocaleString('en-IN')}
                    </span>
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                  <span className="text-[11px] font-bold text-muted-foreground">
                    Total Income:{' '}
                    <span className="font-mono text-emerald-400">
                      ₹
                      {forecast.predictions
                        .reduce((s, p) => s + p.predicted_income, 0)
                        .toLocaleString('en-IN')}
                    </span>
                  </span>
                </div>
                <div className="ml-auto text-[10px] italic text-muted-foreground">
                  {forecast.note}
                </div>
              </div>
            </div>
          ) : (
            /* Upload Drop Zone (Default) */
            <div
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-1 cursor-pointer flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed transition-all duration-300 ${isDragOver
                  ? 'border-primary bg-primary/5 scale-[1.01]'
                  : 'border-border bg-muted/30 hover:border-primary/40 hover:bg-muted/50'
                }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                className="hidden"
              />

              <motion.div
                animate={isDragOver ? { scale: 1.1, y: -4 } : { scale: 1, y: 0 }}
                className="rounded-2xl bg-primary/10 p-4"
              >
                <Upload className="h-8 w-8 text-primary" />
              </motion.div>

              <div className="text-center">
                <p className="text-sm font-bold text-foreground">
                  {isDragOver ? 'Drop your CSV here' : 'Upload Transaction CSV'}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Drag & drop or click to browse • CSV with date, amount, merchant columns
                </p>
              </div>

              {gatewayOnline === false && (
                <p className="text-[10px] font-bold text-destructive">
                  ⚠ API gateway offline — start it first
                </p>
              )}
            </div>
          )}
        </div>
      </motion.div>

      {/* Row 3: Model Training */}
      {/* Row 3: Model Training Split */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        {/* Left: Training Action */}
        <motion.div
          variants={itemVariants}
          className="relative overflow-hidden rounded-[2rem] border border-border bg-card p-6 shadow-xl"
        >
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-emerald-500/5 to-teal-500/5 opacity-50" />

          <div className="relative z-10">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-xl font-bold text-foreground">
                <Brain className="h-5 w-5 text-emerald-500" />
                Train Global Model
              </h3>
            </div>

            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Upload your full transaction history (CSV or Excel) to train a deep learning model
                (Temporal Fusion Transformer) on your data.
              </p>

              <div className="space-y-2">
                <label className="text-xs font-bold uppercase text-muted-foreground">
                  File Password (Optional)
                </label>
                <input
                  type="password"
                  className="w-full rounded-xl border border-border bg-muted/50 px-4 py-2.5 text-sm font-medium transition-colors focus:border-primary focus:outline-none"
                  placeholder="Enter password if file is encrypted"
                  value={trainingPassword}
                  onChange={e => setTrainingPassword(e.target.value)}
                />
              </div>

              <div className="pt-2">
                <button
                  onClick={() => trainingFileRef.current?.click()}
                  disabled={trainingLoading}
                  className="inline-flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-emerald-500/20 transition-all hover:scale-[1.02] hover:shadow-emerald-500/30 disabled:opacity-50 disabled:hover:scale-100"
                >
                  {trainingLoading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="h-4 w-4" />
                  )}
                  {trainingLoading ? 'Uploading & Queuing...' : 'Upload & Train Model'}
                </button>
                <input
                  ref={trainingFileRef}
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleTrainingFileSelect}
                  className="hidden"
                />
              </div>

              {/* Feedback for upload */}
              {trainingResult && (
                <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3">
                  <div className="flex items-center gap-2 text-emerald-600">
                    <CheckCircle2 className="h-4 w-4" />
                    <span className="text-xs font-bold">Job Queued: {trainingResult.job_id}</span>
                  </div>
                </div>
              )}

              {/* Training Error Popup */}
              <AnimatePresence>
                {trainingError && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="mt-4 rounded-xl border border-destructive/20 bg-destructive/10 p-3"
                  >
                    <div className="flex items-center gap-2 text-destructive">
                      <AlertCircle className="h-4 w-4" />
                      <span className="text-xs font-bold">{trainingError}</span>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
        <motion.div variants={itemVariants}>
          <TrainingJobCard />
        </motion.div>
      </div>
    </motion.div>
  );
}
