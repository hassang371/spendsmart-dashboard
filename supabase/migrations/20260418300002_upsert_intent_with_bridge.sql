-- LLD 010: User intents + scenario forecasting — Migration 3.
--
-- Atomic intent + bridge mutation via SECURITY DEFINER RPC.
--
-- Why an RPC: `IntentsService` must keep `public.user_intents` and the
-- bridged `public.scheduled_cashflows` row consistent. Two separate
-- supabase-py calls cannot guarantee atomicity — a process crash
-- between writes leaves an orphan or stale companion row. Wrapping the
-- two writes in a single PL/pgSQL function gives BEGIN/COMMIT semantics.
--
-- Authorisation:
--   * The function asserts `payload->>'user_id' = auth.uid()::text`.
--     A user cannot upsert another user's intent through this RPC even
--     though it runs SECURITY DEFINER.
--   * The bridged scheduled_cashflows row inherits the same user_id.
--
-- Operations:
--   * INSERT  — id is NULL in payload. Inserts user_intents, then if
--               `should_bridge=true` inserts scheduled_cashflows.
--   * UPDATE  — id provided. Updates user_intents fields; the companion
--               scheduled_cashflows row is updated by source_rule_id
--               lookup. If the intent transitions from non-dated→dated
--               (rare in v1), inserts a new bridge row.
--
-- Refs: docs/features/010-user-intents-and-scenario-forecasting.md
--       §Security Considerations → "Bridge integrity"
--       §Domain Model → "Bridge operations from IntentsService"

CREATE OR REPLACE FUNCTION public.upsert_intent_with_bridge(payload jsonb)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_user_id        uuid;
    v_intent_id      uuid;
    v_intent         public.user_intents%ROWTYPE;
    v_should_bridge  boolean;
    v_bridge_payload jsonb;
    v_existing_bridge_id uuid;
BEGIN
    v_user_id := (payload->>'user_id')::uuid;
    IF v_user_id IS NULL OR v_user_id <> auth.uid() THEN
        RAISE EXCEPTION 'unauthorized: user_id mismatch';
    END IF;

    v_intent_id := NULLIF(payload->>'id', '')::uuid;
    v_should_bridge := COALESCE((payload->>'should_bridge')::boolean, false);
    v_bridge_payload := payload->'bridge_row';

    IF v_intent_id IS NULL THEN
        -- INSERT path
        INSERT INTO public.user_intents (
            user_id, intent_type, amount, amount_delta, category_bucket,
            start_date, end_date, confidence, is_recurring, rrule_freq,
            notes, is_active
        )
        VALUES (
            v_user_id,
            payload->>'intent_type',
            NULLIF(payload->>'amount','')::numeric,
            NULLIF(payload->>'amount_delta','')::numeric,
            NULLIF(payload->>'category_bucket',''),
            (payload->>'start_date')::date,
            NULLIF(payload->>'end_date','')::date,
            COALESCE(payload->>'confidence','medium'),
            COALESCE((payload->>'is_recurring')::boolean, false),
            NULLIF(payload->>'rrule_freq',''),
            NULLIF(payload->>'notes',''),
            COALESCE((payload->>'is_active')::boolean, true)
        )
        RETURNING * INTO v_intent;
    ELSE
        -- UPDATE path
        UPDATE public.user_intents
        SET amount       = COALESCE(NULLIF(payload->>'amount','')::numeric, amount),
            amount_delta = COALESCE(NULLIF(payload->>'amount_delta','')::numeric, amount_delta),
            start_date   = COALESCE(NULLIF(payload->>'start_date','')::date, start_date),
            end_date     = COALESCE(NULLIF(payload->>'end_date','')::date, end_date),
            confidence   = COALESCE(NULLIF(payload->>'confidence',''), confidence),
            notes        = COALESCE(NULLIF(payload->>'notes',''), notes),
            is_active    = COALESCE((payload->>'is_active')::boolean, is_active)
        WHERE id = v_intent_id AND user_id = v_user_id
        RETURNING * INTO v_intent;

        IF NOT FOUND THEN
            RAISE EXCEPTION 'intent not found: %', v_intent_id;
        END IF;
    END IF;

    -- Bridge sync. Only DATED intents (per LLD 010 should_have_bridge_row)
    -- get a scheduled_cashflows row.
    IF v_should_bridge AND v_bridge_payload IS NOT NULL THEN
        SELECT id INTO v_existing_bridge_id
        FROM public.scheduled_cashflows
        WHERE source_rule_id = v_intent.id;

        IF v_existing_bridge_id IS NULL THEN
            INSERT INTO public.scheduled_cashflows (
                user_id, merchant, amount, category_bucket, rrule_freq,
                day_of_month, day_of_week, next_occurrence, end_date,
                confidence, source, is_active, source_rule_id
            )
            VALUES (
                v_user_id,
                v_bridge_payload->>'merchant',
                (v_bridge_payload->>'amount')::numeric,
                v_bridge_payload->>'category_bucket',
                v_bridge_payload->>'rrule_freq',
                NULLIF(v_bridge_payload->>'day_of_month','')::int,
                NULLIF(v_bridge_payload->>'day_of_week','')::int,
                (v_bridge_payload->>'next_occurrence')::date,
                NULLIF(v_bridge_payload->>'end_date','')::date,
                (v_bridge_payload->>'confidence')::float,
                'intent',
                COALESCE((v_bridge_payload->>'is_active')::boolean, v_intent.is_active),
                v_intent.id
            );
        ELSE
            UPDATE public.scheduled_cashflows
            SET amount          = (v_bridge_payload->>'amount')::numeric,
                category_bucket = v_bridge_payload->>'category_bucket',
                rrule_freq      = v_bridge_payload->>'rrule_freq',
                next_occurrence = (v_bridge_payload->>'next_occurrence')::date,
                end_date        = NULLIF(v_bridge_payload->>'end_date','')::date,
                is_active       = COALESCE((v_bridge_payload->>'is_active')::boolean, v_intent.is_active),
                updated_at      = now()
            WHERE id = v_existing_bridge_id;
        END IF;
    ELSIF v_intent_id IS NOT NULL THEN
        -- UPDATE path: mirror is_active onto any existing bridge row.
        UPDATE public.scheduled_cashflows
        SET is_active  = v_intent.is_active,
            updated_at = now()
        WHERE source_rule_id = v_intent.id;
    END IF;

    RETURN to_jsonb(v_intent);
END;
$$;

REVOKE ALL ON FUNCTION public.upsert_intent_with_bridge(jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.upsert_intent_with_bridge(jsonb) TO authenticated;
