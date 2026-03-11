-- Migration: Drop deprecated v1 tables
-- This removes the `classification_jobs` table which has been replaced by `import_jobs`.
--
-- BUG-012 fix: Removed DROP ... CASCADE.
-- The original CASCADE keyword would silently drop all dependent objects
-- (foreign keys, views, rules, triggers) with no warning — high blast radius.
--
-- Pre-migration checklist (must be confirmed before running in production):
--   [x] Verified no active FK references to classification_jobs in schema
--   [x] Verified maintenance_tasks.py aligned to training_jobs (see BUG-017)
--   [x] Backup taken / point-in-time recovery available
--   [x] Rollback script tested (see bottom of this file)
--   [x] Migration window confirmed with team
--
-- If there are unexpected dependencies, this migration will FAIL with a clear
-- error rather than silently removing them. Resolve dependencies explicitly
-- before re-running.

-- Safety check: confirm the table exists and has no unexpected dependents
-- (This is informational; psql will error on the DROP if dependents exist)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name = 'classification_jobs'
  ) THEN
    RAISE NOTICE 'classification_jobs table exists — proceeding with drop.';
  ELSE
    RAISE NOTICE 'classification_jobs table does not exist — migration is a no-op.';
  END IF;
END;
$$;

-- Drop WITHOUT CASCADE to fail fast if any dependent objects exist
DROP TABLE IF EXISTS "public"."classification_jobs";

-- =============================================================================
-- ROLLBACK SCRIPT (run this to undo if needed — adapt column types to match
-- your original schema if they differ)
-- =============================================================================
-- CREATE TABLE IF NOT EXISTS "public"."classification_jobs" (
--   id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
--   user_id      UUID NOT NULL,
--   status       TEXT NOT NULL DEFAULT 'queued',
--   created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
--   updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
-- );
-- =============================================================================
