-- Run this in Supabase SQL Editor to fix the leads table
-- Go to: https://supabase.com/dashboard/project/qmjwnfmcdepibytbirbl/sql/new

ALTER TABLE leads 
  ADD COLUMN IF NOT EXISTS lead_status text DEFAULT 'NEW',
  ADD COLUMN IF NOT EXISTS scraping_method text,
  ADD COLUMN IF NOT EXISTS scraping_status text,
  ADD COLUMN IF NOT EXISTS lead_quality text,
  ADD COLUMN IF NOT EXISTS ai_reason text,
  ADD COLUMN IF NOT EXISTS source_platform text,
  ADD COLUMN IF NOT EXISTS source_url text,
  ADD COLUMN IF NOT EXISTS source_title text,
  ADD COLUMN IF NOT EXISTS full_name text,
  ADD COLUMN IF NOT EXISTS company_name text,
  ADD COLUMN IF NOT EXISTS phone text,
  ADD COLUMN IF NOT EXISTS website text,
  ADD COLUMN IF NOT EXISTS location text,
  ADD COLUMN IF NOT EXISTS project_title text,
  ADD COLUMN IF NOT EXISTS project_description text,
  ADD COLUMN IF NOT EXISTS technologies jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS services_required jsonb DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS budget text,
  ADD COLUMN IF NOT EXISTS currency text,
  ADD COLUMN IF NOT EXISTS timeline text,
  ADD COLUMN IF NOT EXISTS lead_type text,
  ADD COLUMN IF NOT EXISTS posted_date text,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
