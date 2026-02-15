-- Migration: 001_active_learning

-- 1. Add manual override flag to transactions
ALTER TABLE transactions 
ADD COLUMN IF NOT EXISTS is_manual BOOLEAN DEFAULT FALSE;

-- 2. Create classification_jobs table
CREATE TABLE IF NOT EXISTS classification_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    transaction_ids UUID[], -- Optional: if limiting to specific transactions
    logs TEXT
);

-- 3. RLS for classification_jobs
ALTER TABLE classification_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own classification jobs"
ON classification_jobs FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own classification jobs"
ON classification_jobs FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- 4. Create training_jobs table if it doesn't exist (it was referenced in worker code but might be missing in schema.sql)
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    checkpoint_path TEXT,
    metrics JSONB,
    logs TEXT,
    transaction_count INTEGER
);

ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own training jobs"
ON training_jobs FOR SELECT
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own training jobs"
ON training_jobs FOR INSERT
WITH CHECK (auth.uid() = user_id);
