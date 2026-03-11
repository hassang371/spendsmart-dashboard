-- Migration: Create 'models' storage bucket for ML-1 Model Versioning Registry

-- 1. Insert bucket if it doesn't exist
INSERT INTO storage.buckets (id, name, public)
VALUES ('models', 'models', false)
ON CONFLICT (id) DO NOTHING;

-- 2. Allow authenticated users to upload and read their own models
CREATE POLICY "Users can upload their own models"
ON storage.objects FOR INSERT TO authenticated
WITH CHECK (
  bucket_id = 'models' AND
  (storage.foldername(name))[1] = auth.uid()::text
);

CREATE POLICY "Users can read their own models"
ON storage.objects FOR SELECT TO authenticated
USING (
  bucket_id = 'models' AND
  (storage.foldername(name))[1] = auth.uid()::text
);

-- Note: We might also want service role to bypass these policies,
-- but service roles bypass RLS by default.
