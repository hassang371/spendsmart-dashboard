-- =============================================================================
-- Baseline migration: bootstrap tables that exist on remote prod but were
-- never CREATEd by a local migration.
--
-- Why this file exists
-- --------------------
-- Several public.* tables (transactions, training_jobs, training_corrections,
-- import_jobs) were originally created on the remote Supabase project via
-- the `mcp__supabase__execute_sql` MCP path during early SCALE development
-- and never bootstrapped into a local migration. Subsequent migrations
-- (e.g. 20260228010000_add_m2_indexes.sql) ALTER those tables — which means
-- `supabase db reset` against an empty local DB fails because the tables do
-- not exist yet.
--
-- This baseline reconstructs those tables in their *earliest* shape — that
-- is, without later columns / constraints / indexes that subsequent dated
-- migrations are responsible for adding. Each later migration must continue
-- to apply cleanly on top of this baseline.
--
-- The file is fully idempotent (CREATE ... IF NOT EXISTS, DROP POLICY IF
-- EXISTS, etc.) so it can be re-run safely against the already-populated
-- remote project. We never push this migration to remote (the remote schema
-- is already there); this file exists purely to make local `db reset` work.
--
-- Scope decision
-- --------------
-- We restore the *earliest* form of each missing table — without:
--   * transactions.account_id  (added by 20260315000001)
--   * training_jobs.source_row_count / date_range_start / date_range_end /
--     data_fingerprint (added by 20260309000002)
--   * 'queued' status in training_jobs CHECK (relaxed by 20260316000001)
-- This guarantees later ALTER migrations apply cleanly without conflict.
--
-- Important wrinkle — the fingerprint column
-- ------------------------------------------
-- The historical migration 20260309000000_add_transaction_fingerprint.sql
-- creates `idx_transactions_fingerprint` as a partial unique index
-- (WHERE fingerprint IS NOT NULL) and then attaches it via
--   ALTER TABLE … ADD CONSTRAINT … UNIQUE USING INDEX idx_transactions_fingerprint
-- PostgreSQL rejects this combination — partial indexes cannot back a
-- UNIQUE constraint (error 42809). On the remote project the migration
-- was clearly applied via a different path (the index ended up
-- non-partial), but locally the file as-written cannot run.
-- Symmetrically, 20260310000000_fix_fingerprint_unique.sql repeats the same
-- pattern with `idx_transactions_user_fingerprint`.
--
-- We are not allowed to modify those migration files. Workaround: this
-- baseline pre-creates both the `fingerprint` column and the two backing
-- indexes as **non-partial** unique indexes. The `IF NOT EXISTS` guards
-- on the later migrations skip the partial CREATE, and the subsequent
-- ADD CONSTRAINT … USING INDEX succeeds because the index it picks up
-- is non-partial.
--
-- Refs:
--   docs/plans/2026-04-17-prediction-engine-v1-master.md — Stage 10
--   docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Required extension (used by transactions.id default)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" SCHEMA extensions;

-- ---------------------------------------------------------------------------
-- public.transactions  (earliest form — no fingerprint, no account_id)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.transactions (
    id               UUID PRIMARY KEY DEFAULT extensions.uuid_generate_v4(),
    user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    transaction_date TIMESTAMPTZ NOT NULL,
    amount           NUMERIC(12, 2) NOT NULL,
    currency         VARCHAR(3) DEFAULT 'INR',
    description      TEXT,
    merchant_name    TEXT,
    category         TEXT DEFAULT 'Uncategorized',
    payment_method   TEXT,
    status           TEXT DEFAULT 'completed',
    created_at       TIMESTAMPTZ DEFAULT now(),
    raw_data         JSONB,
    type             TEXT,
    is_manual          BOOLEAN DEFAULT FALSE,
    suggested_category TEXT,
    confidence_score   DOUBLE PRECISION,
    informative_text   TEXT,
    bank_name          TEXT,
    -- See "Important wrinkle" above: pre-create the column so the broken
    -- partial-index constraint pattern in 20260309 / 20260310 collapses to
    -- a no-op with the non-partial indexes we install below.
    fingerprint        TEXT
);

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

-- Indexes. Two categories:
--   1. Indexes that exist on remote but are NOT created by any later
--      migration (idx_transactions_user_date, idx_transactions_category)
--      → must be in baseline, end of story.
--   2. Indexes that 20260228010000_add_m2_indexes.sql creates with
--      CREATE INDEX CONCURRENTLY (pagination, user_merchant, user_amount,
--      raw_data) → also created here as plain (non-CONCURRENT) indexes
--      with IF NOT EXISTS so the later migration is a no-op locally.
--      We can't strip CONCURRENTLY from that migration (constraint: don't
--      alter existing migrations) and CONCURRENTLY can't run inside the
--      single-pipeline transaction the supabase CLI uses for `db reset`.
--      Pre-creating the indexes here is the only path that lets
--      `db reset` succeed without touching migration history.
CREATE INDEX IF NOT EXISTS idx_transactions_user_date
    ON public.transactions (user_id, transaction_date);
CREATE INDEX IF NOT EXISTS idx_transactions_category
    ON public.transactions (category);
CREATE INDEX IF NOT EXISTS idx_transactions_pagination
    ON public.transactions (user_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_user_merchant
    ON public.transactions (user_id, merchant_name);
CREATE INDEX IF NOT EXISTS idx_transactions_user_amount
    ON public.transactions (user_id, amount);
CREATE INDEX IF NOT EXISTS idx_transactions_raw_data
    ON public.transactions USING GIN (raw_data);

-- Non-partial unique indexes keyed on fingerprint. See "Important wrinkle"
-- in the header. These exist solely so 20260309000000 and 20260310000000
-- — both of which try to back a UNIQUE constraint with a partial index
-- and fail with SQLSTATE 42809 — can collapse to no-ops:
--   * 20260309 step "CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_fingerprint"
--     skips because the name exists.
--   * 20260309 step "ADD CONSTRAINT transactions_fingerprint_key
--     UNIQUE USING INDEX idx_transactions_fingerprint" attaches our
--     non-partial index — succeeds.
--   * 20260310 drops both, then repeats the pattern for
--     idx_transactions_user_fingerprint — same behaviour.
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_fingerprint
    ON public.transactions (fingerprint);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transactions_user_fingerprint
    ON public.transactions (user_id, fingerprint);

-- RLS policies (baseline — tenant isolation). Drop-and-create for idempotency
-- so re-running the baseline never trips on existing policies.
DROP POLICY IF EXISTS "Users can view own transactions" ON public.transactions;
CREATE POLICY "Users can view own transactions"
    ON public.transactions FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert own transactions" ON public.transactions;
CREATE POLICY "Users can insert own transactions"
    ON public.transactions FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can update own transactions" ON public.transactions;
CREATE POLICY "Users can update own transactions"
    ON public.transactions FOR UPDATE
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete own transactions" ON public.transactions;
CREATE POLICY "Users can delete own transactions"
    ON public.transactions FOR DELETE
    USING (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- public.training_jobs  (earliest form — no lineage cols, restrictive CHECK)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.training_jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    status            TEXT DEFAULT 'pending',
    logs              TEXT,
    created_at        TIMESTAMPTZ DEFAULT now(),
    updated_at        TIMESTAMPTZ DEFAULT now(),
    checkpoint_path   TEXT,
    metrics           JSONB,
    transaction_count INTEGER,
    -- Earliest CHECK — does not include 'queued'. 20260316000001 relaxes this
    -- to add 'queued' / 'processing' / 'failed' / 'completed' / 'running'.
    CONSTRAINT training_jobs_status_check
        CHECK (status = ANY (ARRAY['pending'::text, 'running'::text, 'completed'::text, 'failed'::text]))
);

ALTER TABLE public.training_jobs ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS training_jobs_status_idx
    ON public.training_jobs (status);
-- See note above on transactions indexes — pre-create the m2 composite
-- index here (plain, not CONCURRENT) so the later CONCURRENTLY migration
-- becomes a no-op under `supabase db reset`.
CREATE INDEX IF NOT EXISTS idx_training_jobs_user_status
    ON public.training_jobs (user_id, status, created_at DESC);

DROP POLICY IF EXISTS "Users can view their own jobs" ON public.training_jobs;
CREATE POLICY "Users can view their own jobs"
    ON public.training_jobs FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own jobs" ON public.training_jobs;
CREATE POLICY "Users can insert their own jobs"
    ON public.training_jobs FOR INSERT
    WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can delete their own jobs" ON public.training_jobs;
CREATE POLICY "Users can delete their own jobs"
    ON public.training_jobs FOR DELETE
    USING (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- public.training_corrections
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.training_corrections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    transaction_id      UUID REFERENCES public.transactions(id) ON DELETE CASCADE,
    description         TEXT NOT NULL,
    original_category   TEXT,
    corrected_category  TEXT NOT NULL,
    created_at          TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE public.training_corrections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own corrections" ON public.training_corrections;
CREATE POLICY "Users can view their own corrections"
    ON public.training_corrections FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users can insert their own corrections" ON public.training_corrections;
CREATE POLICY "Users can insert their own corrections"
    ON public.training_corrections FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- public.import_jobs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.import_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id),
    status              TEXT NOT NULL DEFAULT 'pending',
    filename            TEXT,
    total_parsed        INTEGER DEFAULT 0,
    inserted            INTEGER DEFAULT 0,
    skipped_duplicates  INTEGER DEFAULT 0,
    classified          INTEGER DEFAULT 0,
    timings             JSONB DEFAULT '{}'::jsonb,
    error_message       TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    CONSTRAINT import_jobs_status_check
        CHECK (status = ANY (ARRAY[
            'pending'::text, 'parsing'::text, 'inserting'::text,
            'classifying'::text, 'complete'::text, 'failed'::text,
            'cancelled'::text
        ]))
);

ALTER TABLE public.import_jobs ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS idx_import_jobs_user_created
    ON public.import_jobs (user_id, created_at DESC);

DROP POLICY IF EXISTS "Users can view own import jobs" ON public.import_jobs;
CREATE POLICY "Users can view own import jobs"
    ON public.import_jobs FOR SELECT
    USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Service role full access on import_jobs" ON public.import_jobs;
CREATE POLICY "Service role full access on import_jobs"
    ON public.import_jobs FOR ALL
    USING (true) WITH CHECK (true);
