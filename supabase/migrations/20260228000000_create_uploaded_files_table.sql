-- Migration: Create uploaded_files table
-- Description: Tracks files uploaded for ingestion, forecasting, and training.

CREATE TABLE IF NOT EXISTS public.uploaded_files (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    transaction_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.uploaded_files ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Users can view their own uploaded files"
    ON public.uploaded_files FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own uploaded files"
    ON public.uploaded_files FOR INSERT
    TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own uploaded files"
    ON public.uploaded_files FOR UPDATE
    TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own uploaded files"
    ON public.uploaded_files FOR DELETE
    TO authenticated
    USING (auth.uid() = user_id);

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_uploaded_files_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_uploaded_files_modtime
    BEFORE UPDATE ON public.uploaded_files
    FOR EACH ROW
    EXECUTE PROCEDURE update_uploaded_files_updated_at();

-- Create indices for performant queries
CREATE INDEX IF NOT EXISTS idx_uploaded_files_user_id ON public.uploaded_files(user_id);
