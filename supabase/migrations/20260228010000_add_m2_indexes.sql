-- M2: Database optimization indexes for pagination, filtering, and query performance
-- Applied via Supabase MCP on 2026-02-28
-- BUG-029 fix: All indexes now use CREATE INDEX CONCURRENTLY to avoid write locks
-- on large tables during migration windows.
-- NOTE: CONCURRENTLY cannot run inside a transaction block. This file must be
-- executed outside of a transaction (i.e. as a non-transactional migration).

-- Keyset pagination index (critical for cursor-based pagination)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_pagination
  ON public.transactions (user_id, created_at DESC, id DESC);

-- Merchant filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_merchant
  ON public.transactions (user_id, merchant_name);

-- Amount range filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_user_amount
  ON public.transactions (user_id, amount);

-- JSONB raw_data queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_transactions_raw_data
  ON public.transactions USING GIN (raw_data);

-- Training jobs composite (user + status + date)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_training_jobs_user_status
  ON public.training_jobs (user_id, status, created_at DESC);
