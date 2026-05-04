-- LLD 010: User intents + scenario forecasting — Migration 2.
--
-- Adds `source_rule_id` FK column to `public.scheduled_cashflows`.
-- This column links bridge rows back to their originating
-- `public.user_intents(id)`, enabling:
--   1. Soft-delete bridge sync — `IntentsService` looks up the
--      companion row by `source_rule_id` instead of replaying the
--      whole composite key.
--   2. Hard-delete cascade — when an intent is hard-deleted (only
--      possible via `auth.users` ON DELETE CASCADE → user_intents
--      ON DELETE CASCADE), the bridged scheduled_cashflows row
--      cascades automatically.
--
-- Two-level cascade contract:
--   auth.users ─CASCADE→ user_intents ─CASCADE→ scheduled_cashflows
--                                              (where source='intent')
--
-- Refs: docs/features/010-user-intents-and-scenario-forecasting.md
--       §Database Changes (Migration 2)
--       §Testing Strategy → Contract Tests → "Two-level cascade"

ALTER TABLE public.scheduled_cashflows
    ADD COLUMN source_rule_id uuid
        REFERENCES public.user_intents(id) ON DELETE CASCADE;

CREATE INDEX idx_scheduled_cashflows_source_rule
    ON public.scheduled_cashflows (source_rule_id)
    WHERE source = 'intent';
