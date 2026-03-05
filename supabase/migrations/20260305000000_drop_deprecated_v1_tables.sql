-- Migration: Drop deprecated v1 tables
-- This removes the `classification_jobs` table which has been replaced entirely by `import_jobs`.

DROP TABLE IF EXISTS "public"."classification_jobs" CASCADE;
