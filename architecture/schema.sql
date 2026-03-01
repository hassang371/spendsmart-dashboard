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

-- Policy: Users can only view their own transactions
CREATE POLICY "Users can view own transactions" 
ON transactions FOR SELECT 
USING (auth.uid() = user_id);

-- Policy: Users can insert their own transactions
CREATE POLICY "Users can insert own transactions" 
ON transactions FOR INSERT 
WITH CHECK (auth.uid() = user_id);

-- Policy: Users can update own transactions
CREATE POLICY "Users can update own transactions" 
ON transactions FOR UPDATE 
USING (auth.uid() = user_id);

-- Policy: Users can delete own transactions
CREATE POLICY "Users can delete own transactions"
ON transactions FOR DELETE
USING (auth.uid() = user_id);

-- 4. Uploaded Files Table (deduplication by file hash)
CREATE TABLE IF NOT EXISTS uploaded_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    file_hash TEXT NOT NULL,
    filename TEXT,
    upload_type TEXT DEFAULT 'import',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, file_hash)
);

ALTER TABLE uploaded_files ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own uploaded files"
ON uploaded_files FOR ALL
USING (auth.uid() = user_id);

-- 5. Training Jobs Table
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    celery_task_id TEXT,
    logs TEXT,
    metrics JSONB,
    checkpoint_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own training jobs"
ON training_jobs FOR SELECT
USING (auth.uid() = user_id);
-- Service role manages all training job updates (Celery workers bypass RLS)
CREATE POLICY "Service role can manage training jobs"
ON training_jobs FOR ALL
USING (true);

-- 6. Classification Jobs Table
CREATE TABLE IF NOT EXISTS classification_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    logs TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE classification_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own classification jobs"
ON classification_jobs FOR SELECT
USING (auth.uid() = user_id);
