-- Protocol: B.L.A.S.T. / Phase 3

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Transactions Table
CREATE TABLE IF NOT EXISTS transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
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
    original_category TEXT,
    is_manual BOOLEAN DEFAULT FALSE,

    -- Constraints
    -- No CHECK on amount: cancelled transactions have amount=0
);

-- 2. Indexes
CREATE INDEX IF NOT EXISTS idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category);
-- Cursor-based pagination orders by (user_id, created_at DESC)
CREATE INDEX IF NOT EXISTS idx_transactions_user_created ON transactions(user_id, created_at DESC);
-- Fingerprint deduplication unique constraint (used by upsert and import dedup)
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_fingerprint
    ON transactions(user_id, fingerprint)
    WHERE fingerprint IS NOT NULL;

-- 3. RLS Policies
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

-- 4. Uploaded Files Table (deduplication by file hash)
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

-- 5. Training Jobs Table
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    logs TEXT,
    metrics JSONB,
    checkpoint_path TEXT,
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

-- 6. Classification Jobs Table
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

-- 7. Training Corrections Table (Active Learning)
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

-- 8. User Model Metadata
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
