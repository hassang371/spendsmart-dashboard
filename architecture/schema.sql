-- Protocol: B.L.A.S.T. / Phase 3

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Bank Accounts Table (Account Aggregator)
-- Must be defined before transactions (transactions.account_id references bank_accounts.id)
CREATE TABLE IF NOT EXISTS public.bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'savings',
    institution TEXT,
    provider TEXT,
    provider_account_id TEXT,
    consent_id TEXT,
    consent_status TEXT NOT NULL DEFAULT 'none',
    consent_expiry TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ,
    sync_status TEXT NOT NULL DEFAULT 'idle',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_manual BOOLEAN NOT NULL DEFAULT FALSE,
    masked_number TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX idx_bank_accounts_user ON public.bank_accounts (user_id);

-- Provider account uniqueness (only for non-null provider accounts)
CREATE UNIQUE INDEX idx_bank_accounts_provider_account
    ON public.bank_accounts (user_id, provider_account_id)
    WHERE provider_account_id IS NOT NULL;

-- Only one manual account per user
CREATE UNIQUE INDEX idx_bank_accounts_user_manual
    ON public.bank_accounts (user_id)
    WHERE is_manual = TRUE;

-- RLS
ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own accounts"
    ON public.bank_accounts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own accounts"
    ON public.bank_accounts FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own accounts"
    ON public.bank_accounts FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete non-manual accounts"
    ON public.bank_accounts FOR DELETE
    USING (auth.uid() = user_id AND is_manual = FALSE);

-- Service role bypass for worker sync
CREATE POLICY "Service role has full access to bank_accounts"
    ON public.bank_accounts FOR ALL
    TO service_role
    USING (true) WITH CHECK (true);

-- 2. Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    transaction_date TIMESTAMP WITH TIME ZONE NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'INR',
    description TEXT,
    merchant_name TEXT,
    category TEXT DEFAULT 'Uncategorized',
    payment_method TEXT,
    status TEXT DEFAULT 'completed',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    raw_data JSONB,
    fingerprint TEXT,
    type TEXT DEFAULT 'debit',
    is_manual BOOLEAN DEFAULT FALSE,
    suggested_category TEXT,
    confidence_score   FLOAT,
    -- Parsed during ingestion by cleaner.process_description()
    informative_text   TEXT,
    bank_name          TEXT,

    -- Constraints
    -- No CHECK on amount: cancelled transactions have amount=0
);

-- 3. Indexes
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
-- Cursor-based pagination orders by (user_id, created_at DESC)
CREATE INDEX IF NOT EXISTS idx_transactions_user_created ON transactions(user_id, created_at DESC);
-- Fingerprint deduplication unique index scoped to account_id (used by upsert and import dedup)
-- Note: PostgreSQL does not support ADD CONSTRAINT UNIQUE USING INDEX on partial indexes.
-- Uniqueness is enforced by the index itself; use ON CONFLICT (account_id, fingerprint)
-- WHERE fingerprint IS NOT NULL in application upserts.
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_account_fingerprint
    ON transactions(account_id, fingerprint)
    WHERE fingerprint IS NOT NULL;

-- 4. RLS Policies
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own transactions"
ON transactions FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own transactions"
ON transactions FOR INSERT
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own transactions"
ON transactions FOR UPDATE
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own transactions"
ON transactions FOR DELETE
USING (auth.uid() = user_id);

-- 5. Uploaded Files Table (deduplication by file hash)
CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    file_hash TEXT NOT NULL,
    filename TEXT,
    upload_type TEXT DEFAULT 'import',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, file_hash),
    -- upload_type values: 'import' (bank statement), 'training' (labelled CSV), 'forecast' (predict CSV)
    CONSTRAINT uploaded_files_upload_type_check
        CHECK (upload_type = ANY (ARRAY['training'::text, 'forecast'::text, 'import'::text]))
);

ALTER TABLE uploaded_files ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own uploaded files"
ON uploaded_files FOR ALL
USING (auth.uid() = user_id);

-- 6. Training Jobs Table
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    logs TEXT,
    metrics JSONB,
    checkpoint_path TEXT,   -- DEPRECATED: v2 classifier uses user_model_metadata.adapter_url instead
    transaction_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- status values: pending → running → completed | failed
    CONSTRAINT training_jobs_status_check
        CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'processing'::text, 'completed'::text, 'failed'::text]))
);

ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own training jobs"
ON training_jobs FOR SELECT
USING (auth.uid() = user_id);
-- Service role manages all training job updates (background workers bypass RLS)
CREATE POLICY "Service role can manage training jobs"
ON training_jobs FOR ALL
USING (true);

-- 7. Classification Jobs Table
-- NOTE: v3 ingestion classifies inline in background tasks; this table may be unused
CREATE TABLE IF NOT EXISTS classification_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    logs TEXT,
    transaction_ids UUID[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE classification_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own classification jobs"
ON classification_jobs FOR SELECT
USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own classification jobs"
ON classification_jobs FOR INSERT
WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own classification jobs"
ON classification_jobs FOR UPDATE
USING (auth.uid() = user_id);
CREATE POLICY "Users can delete own classification jobs"
ON classification_jobs FOR DELETE
USING (auth.uid() = user_id);

-- 8. Training Corrections Table (Active Learning)
CREATE TABLE IF NOT EXISTS training_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    transaction_id UUID REFERENCES transactions(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    original_category TEXT,
    corrected_category TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE training_corrections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own training corrections"
ON training_corrections FOR SELECT
USING (auth.uid() = user_id);
CREATE POLICY "Users can insert own training corrections"
ON training_corrections FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- 9. User Model Metadata
CREATE TABLE IF NOT EXISTS public.user_model_metadata (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    adapter_url TEXT,
    correction_count INT NOT NULL DEFAULT 0,
    adapter_updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.user_model_metadata ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own model metadata"
ON public.user_model_metadata FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can upsert own model metadata"
ON public.user_model_metadata FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update own model metadata"
ON public.user_model_metadata FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "Service role has full access"
ON public.user_model_metadata TO service_role USING (true) WITH CHECK (true);
