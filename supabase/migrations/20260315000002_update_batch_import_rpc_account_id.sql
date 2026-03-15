-- Migration: update batch_import_transactions to accept account_id parameter

-- Drop old 2-arg overload (constraint it relied on was dropped in 20260315000001)
DROP FUNCTION IF EXISTS public.batch_import_transactions(UUID, JSONB);

CREATE OR REPLACE FUNCTION public.batch_import_transactions(
    p_user_id UUID,
    p_account_id UUID,
    p_rows JSONB
)
RETURNS TABLE(inserted_count INTEGER, skipped_count INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    total_rows INTEGER;
    actual_inserted INTEGER;
BEGIN
    total_rows := jsonb_array_length(p_rows);

    INSERT INTO public.transactions (
        user_id, account_id, transaction_date, amount, currency,
        description, merchant_name, payment_method, status, type,
        fingerprint, informative_text, bank_name, raw_data,
        category, suggested_category, confidence_score
    )
    SELECT
        p_user_id,
        p_account_id,
        (row_data->>'transaction_date')::TIMESTAMPTZ,
        (row_data->>'amount')::NUMERIC,
        COALESCE(row_data->>'currency', 'INR'),
        row_data->>'description',
        row_data->>'merchant_name',
        row_data->>'payment_method',
        COALESCE(row_data->>'status', 'completed'),
        COALESCE(row_data->>'type', 'debit'),
        row_data->>'fingerprint',
        row_data->>'informative_text',
        row_data->>'bank_name',
        (row_data->'raw_data')::JSONB,
        COALESCE(row_data->>'category', 'Uncategorized'),
        row_data->>'suggested_category',
        (row_data->>'confidence_score')::FLOAT
    FROM jsonb_array_elements(p_rows) AS row_data
    ON CONFLICT (account_id, fingerprint) WHERE fingerprint IS NOT NULL
    DO NOTHING;

    GET DIAGNOSTICS actual_inserted = ROW_COUNT;
    RETURN QUERY SELECT actual_inserted, (total_rows - actual_inserted);
END;
$$;
