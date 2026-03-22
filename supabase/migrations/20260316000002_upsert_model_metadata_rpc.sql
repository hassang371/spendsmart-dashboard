-- Migration: Atomic upsert_model_metadata RPC
-- Bug 1: save_version() never populated user_model_metadata.
-- This RPC atomically sets adapter_url + adapter_updated_at and
-- increments correction_count in a single statement, eliminating
-- the read-modify-write race condition.

CREATE OR REPLACE FUNCTION public.upsert_model_metadata(
    p_user_id        UUID,
    p_adapter_url    TEXT,
    p_count_delta    INT DEFAULT 0
)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
    INSERT INTO public.user_model_metadata
        (user_id, adapter_url, adapter_updated_at, correction_count)
    VALUES
        (p_user_id, p_adapter_url, NOW(), p_count_delta)
    ON CONFLICT (user_id)
    DO UPDATE SET
        adapter_url        = EXCLUDED.adapter_url,
        adapter_updated_at = EXCLUDED.adapter_updated_at,
        correction_count   = public.user_model_metadata.correction_count
                             + EXCLUDED.correction_count;
$$;

-- Grant execute to service_role (used by background tasks)
GRANT EXECUTE ON FUNCTION public.upsert_model_metadata TO service_role;
