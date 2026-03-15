-- Create bank_accounts table
CREATE TABLE IF NOT EXISTS public.bank_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    account_name TEXT NOT NULL,
    account_type TEXT NOT NULL DEFAULT 'savings',
    institution TEXT,
    provider TEXT,
    provider_account_id TEXT,
    consent_id TEXT,
    consent_status TEXT NOT NULL DEFAULT 'none',
    consent_expiry TIMESTAMPTZ,
    last_synced_at TIMESTAMPTZ,
    sync_status TEXT NOT NULL DEFAULT 'idle',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    is_manual BOOLEAN NOT NULL DEFAULT FALSE,
    masked_number TEXT,
    currency TEXT NOT NULL DEFAULT 'INR',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bank_accounts_user ON public.bank_accounts (user_id);

-- Provider account uniqueness (only for non-null provider accounts)
CREATE UNIQUE INDEX IF NOT EXISTS idx_bank_accounts_provider_account
    ON public.bank_accounts (user_id, provider_account_id)
    WHERE provider_account_id IS NOT NULL;

-- Only one manual account per user
CREATE UNIQUE INDEX IF NOT EXISTS idx_bank_accounts_user_manual
    ON public.bank_accounts (user_id)
    WHERE is_manual = TRUE;

-- RLS
ALTER TABLE public.bank_accounts ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'bank_accounts' AND policyname = 'Users can view own accounts'
    ) THEN
        CREATE POLICY "Users can view own accounts"
            ON public.bank_accounts FOR SELECT
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'bank_accounts' AND policyname = 'Users can insert own accounts'
    ) THEN
        CREATE POLICY "Users can insert own accounts"
            ON public.bank_accounts FOR INSERT
            WITH CHECK (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'bank_accounts' AND policyname = 'Users can update own accounts'
    ) THEN
        CREATE POLICY "Users can update own accounts"
            ON public.bank_accounts FOR UPDATE
            USING (auth.uid() = user_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'bank_accounts' AND policyname = 'Users can delete non-manual accounts'
    ) THEN
        CREATE POLICY "Users can delete non-manual accounts"
            ON public.bank_accounts FOR DELETE
            USING (auth.uid() = user_id AND is_manual = FALSE);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE tablename = 'bank_accounts' AND policyname = 'Service role has full access to bank_accounts'
    ) THEN
        CREATE POLICY "Service role has full access to bank_accounts"
            ON public.bank_accounts FOR ALL
            TO service_role
            USING (true) WITH CHECK (true);
    END IF;
END $$;
