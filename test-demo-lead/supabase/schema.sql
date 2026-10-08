-- Supabase Database Schema for IT Lead Finder (MVP)

CREATE TABLE IF NOT EXISTS search_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    query TEXT NOT NULL,
    platform TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS search_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_id UUID REFERENCES search_queries(id),
    status TEXT NOT NULL,
    urls_found INTEGER DEFAULT 0,
    urls_processed INTEGER DEFAULT 0,
    leads_found INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_urls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    url TEXT NOT NULL UNIQUE,
    platform TEXT,
    title TEXT,
    snippet TEXT,
    search_query TEXT,
    status TEXT,
    scraping_method TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name TEXT,
    company_name TEXT,
    email TEXT,
    phone TEXT,
    whatsapp TEXT,
    website TEXT,
    location TEXT,
    project_title TEXT,
    project_description TEXT,
    technologies JSONB,
    services_required JSONB,
    budget TEXT,
    currency TEXT,
    timeline TEXT,
    lead_type TEXT,
    lead_status TEXT,
    lead_quality TEXT,
    lead_score INTEGER,
    source_platform TEXT,
    source_url TEXT UNIQUE,
    source_title TEXT,
    posted_date TIMESTAMP WITH TIME ZONE,
    scraping_method TEXT,
    ai_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
