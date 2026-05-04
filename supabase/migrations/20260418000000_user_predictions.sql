-- RFC-003: Prediction logging foundation.
--
-- Creates `public.user_predictions` (one row per forecast call, deduped per
-- (user_id, generated_hour) bucket), enables RLS, and exposes a
-- SECURITY DEFINER RPC `log_user_prediction(payload jsonb)` that performs
-- atomic insert-or-no-op. All time-locked / safety-critical fields are
-- derived server-side inside the RPC; the caller-supplied payload only
-- carries content that is either model output or service-controlled
-- bookkeeping (Codex Fix #5/#6 trust-boundary hardening).
--
-- Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §4

CREATE TABLE public.user_predictions (
    prediction_id       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
        -- DEFAULT retained as safety net; application-level INSERTs from
        -- ForecastService supply prediction_id explicitly so the value is
        -- known before the INSERT completes.
    user_id             uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    generated_at        timestamptz NOT NULL DEFAULT now(),
    -- BUG-019: dedup is enforced by a UNIQUE expression index on
    --   (user_id, date_trunc('hour', generated_at, 'UTC'))
    -- The original design used date_trunc('hour', generated_at) — the
    -- two-argument form (text, timestamptz) is STABLE (depends on the
    -- session TimeZone GUC), so PostgreSQL rejects both a STORED
    -- generated column and a unique expression index keyed on it
    -- (SQLSTATE 42P17). The three-argument form
    -- date_trunc(text, timestamptz, text) IS marked IMMUTABLE because
    -- the explicit timezone argument removes the GUC dependency. The
    -- "exactly one row per (user_id, UTC hour)" dedup contract is
    -- preserved bit-for-bit.
    model_type          text        NOT NULL,    -- chronos2 | tft_hybrid | ensemble
    model_version       text        NOT NULL,
    horizon_days        int         NOT NULL CHECK (horizon_days BETWEEN 1 AND 30),
    horizon_end         date        NOT NULL,    -- (generated_at::date + horizon_days)
    forecast            jsonb       NOT NULL,    -- list[ForecastPoint], length = horizon_days, each item carries all 7 quantiles
    variable_importance jsonb,                   -- list[VariableImportance] | null (null for chronos2)
    insights            jsonb       NOT NULL,    -- ForecastInsights snapshot, frozen at insert time
    insights_version    text        NOT NULL,    -- supplied by service; see RFC-003 §"Insights versioning protocol"
    shown_to_user       boolean     NOT NULL DEFAULT true,
    actual_outcomes     jsonb,                   -- filled by evaluate_past_predictions beat task
    mape                float,                   -- P50 MAPE, filled by evaluation task
    pinball_loss        jsonb,                   -- {p2, p10, p25, p50, p75, p90, p98}
    -- Evaluation lease (Codex Fix #2). claimed_at is set when the worker
    -- claims the row; lease_expires_at gives a re-claim deadline so a
    -- crashed/timed-out worker's rows are recoverable. evaluated_at is the
    -- FINAL completion marker, set ONLY after metrics are written. The
    -- unevaluated index keys on evaluated_at.
    claimed_at          timestamptz,
    lease_expires_at    timestamptz,
    evaluated_at        timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Atomic dedup: exactly one row per (user_id, UTC hour). Concurrent
-- INSERTs collide on this constraint and the second one no-ops via
-- ON CONFLICT. Expressed as a unique expression index (BUG-019). Both
-- STORED generated columns and unique expression indexes require
-- IMMUTABLE expressions, so the original two-argument
-- date_trunc('hour', generated_at) was rejected with SQLSTATE 42P17.
-- The three-argument form date_trunc('hour', generated_at, 'UTC') IS
-- IMMUTABLE — the explicit timezone removes the session-GUC dependency.
CREATE UNIQUE INDEX uniq_user_predictions_user_hour
    ON public.user_predictions (user_id, (date_trunc('hour', generated_at, 'UTC')));

CREATE INDEX idx_user_predictions_user_recent
    ON public.user_predictions (user_id, generated_at DESC);

-- Partial index for the evaluation worker's claim query. A row is
-- "claimable" when evaluated_at IS NULL AND (claimed_at IS NULL OR
-- lease_expires_at < now()) — the lease-expiry check happens in the
-- WHERE of the claim query; the partial index keeps only unevaluated
-- rows.
CREATE INDEX idx_user_predictions_unevaluated
    ON public.user_predictions (generated_at)
    WHERE evaluated_at IS NULL;

ALTER TABLE public.user_predictions ENABLE ROW LEVEL SECURITY;

-- Users read only their own predictions.
CREATE POLICY "users select own predictions"
    ON public.user_predictions FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

-- Users INSERT their own predictions via the user-scoped client used by
-- the forecast router. The dedup-correct insert path is the
-- log_user_prediction RPC below; this policy is the RLS backstop that
-- still applies to the SECURITY DEFINER function's INSERT (definer
-- bypasses RLS but the policy documents the intended ownership rule).
CREATE POLICY "users insert own predictions"
    ON public.user_predictions FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

-- Only the service role (evaluation task) updates rows.
CREATE POLICY "system update predictions"
    ON public.user_predictions FOR UPDATE TO service_role
    USING (true) WITH CHECK (true);

-- SECURITY DEFINER RPC for atomic insert-or-no-op.
--
-- Trust boundary (Codex Fix #5/#6):
-- The RPC is grantable to `authenticated` ONLY because every server-owned
-- field that affects ML quality is derived inside the function — not
-- taken from the caller-supplied payload. A malicious authenticated user
-- invoking this RPC directly cannot:
--   * write a row for another user (auth.uid() check)
--   * back-date or future-date a prediction (generated_at = now() ALWAYS)
--   * write a row for an arbitrary horizon (horizon_days clamped 1..30,
--     horizon_end = (now()::date + horizon_days))
--   * pollute model_type with junk strings (validated against allowed set)
--   * write to multiple hour buckets per call (single INSERT,
--     generated_hour auto-derived from now())
--
-- Returns true if a new row was inserted, false if dedup skipped (a row
-- already existed for this (user_id, generated_hour) pair).
CREATE OR REPLACE FUNCTION public.log_user_prediction(payload jsonb)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    inserted_count    int;
    payload_user      uuid    := (payload->>'user_id')::uuid;
    payload_horizon   int     := (payload->>'horizon_days')::int;
    payload_model     text    := payload->>'model_type';
    payload_pred_id   uuid    := (payload->>'prediction_id')::uuid;
    payload_shown     boolean := coalesce((payload->>'shown_to_user')::boolean, true);
    server_generated  timestamptz := now();
    server_horizon_end date;
BEGIN
    -- Tenant guard
    IF payload_user IS NULL OR payload_user <> auth.uid() THEN
        RAISE EXCEPTION 'log_user_prediction: user_id mismatch';
    END IF;

    -- Validate caller-supplied fields BEFORE touching the table.
    IF payload_horizon IS NULL OR payload_horizon < 1 OR payload_horizon > 30 THEN
        RAISE EXCEPTION 'log_user_prediction: horizon_days must be 1..30';
    END IF;
    IF payload_model NOT IN ('chronos2', 'tft_hybrid', 'ensemble') THEN
        RAISE EXCEPTION 'log_user_prediction: invalid model_type';
    END IF;
    IF payload_pred_id IS NULL THEN
        RAISE EXCEPTION 'log_user_prediction: prediction_id required';
    END IF;
    IF (payload->>'insights_version') IS NULL THEN
        RAISE EXCEPTION 'log_user_prediction: insights_version required';
    END IF;
    IF (payload->'forecast') IS NULL THEN
        RAISE EXCEPTION 'log_user_prediction: forecast required';
    END IF;
    IF (payload->'insights') IS NULL THEN
        RAISE EXCEPTION 'log_user_prediction: insights required';
    END IF;

    -- Server-owned: derive the time-locked fields. Caller cannot back-date.
    server_horizon_end := (server_generated::date) + (payload_horizon || ' days')::interval;

    INSERT INTO public.user_predictions (
        prediction_id, user_id, generated_at,
        model_type, model_version, horizon_days, horizon_end,
        forecast, variable_importance, insights, insights_version,
        shown_to_user
    )
    VALUES (
        payload_pred_id,
        payload_user,
        server_generated,                    -- ← server-owned
        payload_model,
        payload->>'model_version',
        payload_horizon,
        server_horizon_end,                  -- ← server-owned
        payload->'forecast',
        payload->'variable_importance',
        payload->'insights',
        payload->>'insights_version',
        payload_shown
    )
    ON CONFLICT (user_id, (date_trunc('hour', generated_at, 'UTC'))) DO NOTHING;

    GET DIAGNOSTICS inserted_count = ROW_COUNT;
    RETURN inserted_count = 1;
END;
$$;

GRANT EXECUTE ON FUNCTION public.log_user_prediction(jsonb) TO authenticated;
