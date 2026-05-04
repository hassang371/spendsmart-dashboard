-- LLD 010: User intents + scenario forecasting — Migration 1.
--
-- Creates `public.user_intents` — the single source of truth for
-- user-declared future events (subscriptions, planned expenses, life
-- events, savings goals, etc.). Dated intents bridge to
-- `public.scheduled_cashflows` via `source='intent'` rows; LIFE_EVENT
-- intents feed RFC-005's stochastic widener at predict time.
--
-- Refs: docs/features/010-user-intents-and-scenario-forecasting.md
--       §Database Changes (Migration 1)
--       §Domain Model
--
-- Migration ordering note: this file MUST apply before
-- 20260418300001_scheduled_cashflows_source_rule_id.sql which adds an
-- FK on `public.user_intents(id)`. The timestamp-prefix sort enforces
-- this ordering under the Supabase migration runner.

CREATE TABLE public.user_intents (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    intent_type      text        NOT NULL CHECK (intent_type IN (
        'income_change','planned_large_expense','life_event',
        'obligation_change','savings_goal','fd_maturity','expected_bonus'
    )),
    amount           numeric,
    amount_delta     numeric,
    category_bucket  text        CHECK (category_bucket IS NULL OR category_bucket IN (
        'salary','rent','groceries','dining','transport','utilities',
        'entertainment','health','emi_loan','investment','transfer','other'
    )),
    start_date       date        NOT NULL,
    end_date         date,
    confidence       text        NOT NULL DEFAULT 'medium' CHECK (confidence IN ('low','medium','high')),
    is_recurring     boolean     NOT NULL DEFAULT false,
    rrule_freq       text        CHECK (rrule_freq IS NULL OR rrule_freq IN (
        'monthly','weekly','biweekly','quarterly','annual'
    )),
    notes            text        CHECK (notes IS NULL OR length(notes) <= 280),
    is_active        boolean     NOT NULL DEFAULT true,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT amount_required_for_dated CHECK (
        intent_type NOT IN (
            'income_change','planned_large_expense','obligation_change',
            'fd_maturity','expected_bonus'
        )
        OR amount IS NOT NULL OR amount_delta IS NOT NULL
    ),
    CONSTRAINT recurring_has_rrule CHECK (
        is_recurring = false OR rrule_freq IS NOT NULL
    ),
    CONSTRAINT savings_goal_has_end_date CHECK (
        intent_type <> 'savings_goal' OR end_date IS NOT NULL
    )
);

-- Auto-update updated_at on row mutation.
CREATE OR REPLACE FUNCTION public.user_intents_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_user_intents_touch_updated_at
BEFORE UPDATE ON public.user_intents
FOR EACH ROW EXECUTE FUNCTION public.user_intents_touch_updated_at();

CREATE INDEX idx_user_intents_user_active
    ON public.user_intents (user_id, is_active, start_date);

ALTER TABLE public.user_intents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users read own intents"
    ON public.user_intents FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "users insert own intents"
    ON public.user_intents FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users update own intents"
    ON public.user_intents FOR UPDATE TO authenticated
    USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- No DELETE policy. Clients soft-delete via is_active=false. Hard-delete
-- only flows from `auth.users` ON DELETE CASCADE.
