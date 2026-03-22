-- Migration: Fix training_jobs status CHECK constraint
-- Bug 5: 'queued' was missing from the allowed set, causing every
-- POST /training/train and POST /training/upload to fail.

ALTER TABLE public.training_jobs
    DROP CONSTRAINT IF EXISTS training_jobs_status_check;

ALTER TABLE public.training_jobs
    ADD CONSTRAINT training_jobs_status_check
    CHECK (status = ANY (ARRAY[
        'pending'::text, 'queued'::text, 'running'::text,
        'processing'::text, 'completed'::text, 'failed'::text
    ]));
