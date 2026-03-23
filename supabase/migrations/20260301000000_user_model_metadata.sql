-- Migration: Create user_model_metadata table
-- Tracks per-user adapter state: storage path, correction count, last updated.

CREATE TABLE IF NOT EXISTS public.user_model_metadata (
    user_id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    adapter_url      TEXT,           -- Supabase Storage path: {user_id}/v_{timestamp}/adapter.pt
    correction_count INT  NOT NULL DEFAULT 0,
    adapter_updated_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.user_model_metadata ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own model metadata"
    ON public.user_model_metadata FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can upsert own model metadata"
    ON public.user_model_metadata FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own model metadata"
    ON public.user_model_metadata FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id);

-- Service role needs full access for background fine-tuning tasks
CREATE POLICY "Service role has full access"
    ON public.user_model_metadata
    TO service_role
    USING (true)
    WITH CHECK (true);
