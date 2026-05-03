-- RFC-005: Three-tier data separation — Layer 1 (deterministic scheduler).
--
-- Creates `public.scheduled_cashflows` for the heuristic recurrence
-- detector + user-override / intent rows (LLD 010 will write
-- source='intent' rows to the same table). Each row is one recurring
-- cashflow rule; projection at inference time expands rules into
-- per-(date, bucket) known-future covariates for the panel TFT.
--
-- Refs: docs/rfcs/RFC-005-aggregation-strategy-three-tier-data-separation.md
--       §Data Model Changes
--
-- ---------------------------------------------------------------------------
-- Pre-apply audit (precautionary; v1 ships against an empty table).
-- Run via psql / `supabase db psql` BEFORE applying this migration to a
-- non-empty environment. Any non-empty result indicates an existing
-- collision under the post-Codex-Fix-#3 unique key — manual merge / dedup
-- required before the migration can complete.
--
--   SELECT user_id, COALESCE(merchant,''), amount, category_bucket, rrule_freq,
--          COALESCE(day_of_month,-1), COALESCE(day_of_week,-1), source,
--          count(*)
--   FROM public.scheduled_cashflows
--   GROUP BY 1,2,3,4,5,6,7,8
--   HAVING count(*) > 1;
-- ---------------------------------------------------------------------------

CREATE TABLE public.scheduled_cashflows (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    merchant         text,
    amount           numeric     NOT NULL,
    category_bucket  text        NOT NULL CHECK (category_bucket IN (
        'salary','rent','groceries','dining','transport','utilities',
        'entertainment','health','emi_loan','investment','transfer','other'
    )),
    rrule_freq       text        NOT NULL CHECK (rrule_freq IN (
        'monthly','weekly','biweekly','quarterly','annual'
    )),
    day_of_month     int         CHECK (day_of_month BETWEEN 1 AND 31),
    day_of_week      int         CHECK (day_of_week BETWEEN 0 AND 6),
    next_occurrence  date        NOT NULL,
    end_date         date,
    confidence       float       NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source           text        NOT NULL CHECK (source IN (
        'heuristic','user_override','intent'
    )),
    is_active        boolean     NOT NULL DEFAULT true,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_scheduled_cashflows_user_active
    ON public.scheduled_cashflows (user_id, is_active, next_occurrence);

-- Codex Fix #3: full recurrence-defining key. Without category_bucket,
-- day_of_month, day_of_week, and source, two genuinely-distinct rules
-- would collide on UPSERT and silently overwrite each other, dropping
-- obligations from the known-future covariate stream.
--
-- COALESCE(...) is required because PostgreSQL treats two NULL values
-- as distinct in unique constraints; using a sentinel (-1, '') folds
-- NULLs into a single representative value so a monthly rule (NULL
-- day_of_week) is uniquely identifiable.
CREATE UNIQUE INDEX uniq_scheduled_cashflows_rule
    ON public.scheduled_cashflows (
        user_id,
        COALESCE(merchant, ''),
        amount,
        category_bucket,
        rrule_freq,
        COALESCE(day_of_month, -1),
        COALESCE(day_of_week,  -1),
        source
    );

ALTER TABLE public.scheduled_cashflows ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users read own scheduled cashflows"
    ON public.scheduled_cashflows FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "users insert own scheduled cashflows"
    ON public.scheduled_cashflows FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users update own scheduled cashflows"
    ON public.scheduled_cashflows FOR UPDATE TO authenticated
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- DELETE not exposed to authenticated users. Garbage-collection of
-- `is_active = false` rows is a service-role maintenance task handled
-- by `apps/api/core/tasks/maintenance_tasks.py` (or a follow-up task).
