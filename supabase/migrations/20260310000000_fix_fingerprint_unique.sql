-- Migration: Fix fingerprint unique constraint to be scoped to user_id
-- We drop the existing index/constraint and create a new one.

-- 1. Drop existing constraint and index
ALTER TABLE public.transactions DROP CONSTRAINT IF EXISTS transactions_fingerprint_key;
DROP INDEX IF EXISTS idx_transactions_fingerprint;

-- 2. Create the correct unique index
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_fingerprint ON public.transactions(user_id, fingerprint) WHERE fingerprint IS NOT NULL;

-- 3. Add the unique constraint to support ON CONFLICT
ALTER TABLE public.transactions
ADD CONSTRAINT transactions_user_fingerprint_key UNIQUE USING INDEX idx_transactions_user_fingerprint;
