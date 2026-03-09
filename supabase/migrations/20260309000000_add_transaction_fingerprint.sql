-- Migration: Add fingerprint column to transactions table for idempotency

-- 1. Add the column
ALTER TABLE public.transactions 
ADD COLUMN IF NOT EXISTS fingerprint TEXT;

-- 2. Add an index to make upserts fast
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_fingerprint ON public.transactions(fingerprint) WHERE fingerprint IS NOT NULL;

-- 3. Add the unique constraint to support ON CONFLICT
ALTER TABLE public.transactions 
ADD CONSTRAINT transactions_fingerprint_key UNIQUE USING INDEX idx_transactions_fingerprint;
