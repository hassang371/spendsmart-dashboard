-- M2: Tune autovacuum for high-churn transactions table
-- Vacuum at 5% dead tuples (default 20%), analyze at 2% changes
-- Applied via Supabase MCP on 2026-02-28

ALTER TABLE public.transactions SET (
  autovacuum_vacuum_scale_factor = 0.05,
  autovacuum_analyze_scale_factor = 0.02,
  autovacuum_vacuum_cost_delay = 2
);
