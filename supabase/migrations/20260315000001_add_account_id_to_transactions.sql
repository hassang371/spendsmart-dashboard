-- Migration: add_account_id_to_transactions
-- Adds account_id FK to transactions, backfills from manual import accounts,
-- and replaces the user-scoped fingerprint index with an account-scoped one.

-- Guard: check for orphan transactions with NULL user_id
DO $$
DECLARE
    orphan_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphan_count FROM public.transactions WHERE user_id IS NULL;
    IF orphan_count > 0 THEN
        RAISE EXCEPTION 'Found % transactions with NULL user_id. Clean up before migration.', orphan_count;
    END IF;
END $$;

-- Add account_id column (nullable initially for backfill)
ALTER TABLE public.transactions
    ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES public.bank_accounts(id);

-- Create manual import account for each existing user (idempotent)
INSERT INTO public.bank_accounts (user_id, account_name, account_type, is_manual, consent_status)
SELECT DISTINCT user_id, 'Manual Import', 'manual', TRUE, 'none'
FROM public.transactions
WHERE user_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM public.bank_accounts ba
      WHERE ba.user_id = transactions.user_id AND ba.is_manual = TRUE
  );

-- Backfill account_id for existing transactions
UPDATE public.transactions t
SET account_id = ba.id
FROM public.bank_accounts ba
WHERE ba.user_id = t.user_id
  AND ba.is_manual = TRUE
  AND t.account_id IS NULL;

-- Now make account_id NOT NULL
ALTER TABLE public.transactions
    ALTER COLUMN account_id SET NOT NULL;

-- Drop old constraint FIRST (required before dropping the index it references)
ALTER TABLE public.transactions
    DROP CONSTRAINT IF EXISTS transactions_user_fingerprint_key;

-- Now drop the old index
DROP INDEX IF EXISTS idx_transactions_user_fingerprint;

-- Create new unique partial index scoped to account_id
-- Note: A named UNIQUE constraint cannot be added via ADD CONSTRAINT UNIQUE USING INDEX
-- on a partial index. Attempting it yields:
--   ERROR 42809: "idx_transactions_account_fingerprint" is a partial index
--   DETAIL: Cannot create a primary key or unique constraint using such an index.
-- This is a PostgreSQL limitation for partial indexes regardless of server version.
-- Uniqueness is enforced by the index itself; use ON CONFLICT (account_id, fingerprint)
-- WHERE fingerprint IS NOT NULL in application upserts.
CREATE UNIQUE INDEX idx_transactions_account_fingerprint
    ON public.transactions (account_id, fingerprint)
    WHERE fingerprint IS NOT NULL;
