-- master_schema.sql
-- This schema lives in the public schema of the master database.
-- Run this file ONCE on a fresh Supabase project to initialize it.

CREATE TABLE IF NOT EXISTS public.tenants (
    id               SERIAL PRIMARY KEY,
    company_name     VARCHAR(100) NOT NULL,
    tenant_id        VARCHAR(50)  UNIQUE NOT NULL,
    hashed_password  TEXT         NOT NULL,
    contact_email    VARCHAR(255) UNIQUE,
    google_sub       VARCHAR(255) UNIQUE,
    email_verified   BOOLEAN      DEFAULT FALSE,
    created_at       TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active        BOOLEAN      DEFAULT TRUE
);

-- Fast login by tenant_id slug
CREATE INDEX IF NOT EXISTS idx_tenant_id
    ON public.tenants(tenant_id);

-- Fast login by email address
CREATE INDEX IF NOT EXISTS idx_tenant_email
    ON public.tenants(contact_email);

-- Fast login by Google OAuth sub
CREATE INDEX IF NOT EXISTS idx_tenant_google_sub
    ON public.tenants(google_sub);

-- Centralized audit logs (optional, for future use)
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id             SERIAL PRIMARY KEY,
    tenant_id      VARCHAR(50) NOT NULL REFERENCES public.tenants(tenant_id),
    action_type    VARCHAR(50) NOT NULL,
    action_details JSONB,
    performed_at   TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);