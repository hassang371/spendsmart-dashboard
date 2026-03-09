-- Migration: Add training lineage fields to training_jobs

ALTER TABLE public.training_jobs
ADD COLUMN IF NOT EXISTS source_row_count INT,
ADD COLUMN IF NOT EXISTS date_range_start DATE,
ADD COLUMN IF NOT EXISTS date_range_end DATE,
ADD COLUMN IF NOT EXISTS data_fingerprint TEXT;
