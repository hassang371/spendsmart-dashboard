-- Training Infrastructure Schema
-- Extends the base schema (schema.sql) with tables for ML training jobs and model management.

-- =============================================================================
-- 1. Add fingerprint column to transactions (for upsert deduplication)
-- =============================================================================
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS fingerprint TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_fingerprint
    ON transactions(user_id, fingerprint);

-- =============================================================================
-- 2. Training Jobs Table
-- =============================================================================
CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    model_type TEXT NOT NULL DEFAULT 'tft',
    logs TEXT,
    checkpoint_path TEXT,
    metrics JSONB,
    transaction_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for worker polling: quickly find pending jobs
CREATE INDEX IF NOT EXISTS idx_training_jobs_pending
    ON training_jobs(status, created_at)
    WHERE status = 'pending';

-- Index for user queries: find latest completed job
CREATE INDEX IF NOT EXISTS idx_training_jobs_user_status
    ON training_jobs(user_id, status, created_at DESC);

-- =============================================================================
-- 3. RLS Policies for training_jobs
-- =============================================================================
ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own training jobs"
    ON training_jobs FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own training jobs"
    ON training_jobs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Note: UPDATE/DELETE by service role only (worker uses service_role key which bypasses RLS).
-- Users should not directly modify job status.

-- =============================================================================
-- 4. Auto-update updated_at trigger
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER training_jobs_updated_at
    BEFORE UPDATE ON training_jobs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
