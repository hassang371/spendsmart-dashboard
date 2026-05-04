-- Adds the partial index keyed on horizon_end so the evaluate_past_predictions
-- claim query (filters horizon_end <= now()::date AND evaluated_at IS NULL)
-- gets the right plan. The Stage 2 migration keyed the existing index on
-- generated_at (Codex Fix #2 lease-bookkeeping queries); this complementary
-- index covers the daily evaluation worker's primary filter without dropping
-- the existing one — both queries (claim by horizon_end, sweep stale leases
-- by generated_at) are now indexed.
--
-- Refs: docs/rfcs/RFC-003-forecast-api-schema-and-prediction-logging.md §5
CREATE INDEX IF NOT EXISTS idx_user_predictions_horizon_end_unevaluated
    ON public.user_predictions (horizon_end)
    WHERE evaluated_at IS NULL;
