-- Creates a dedicated, read-only Postgres role for the Phase 5 dashboard.
--
-- Not a dbmate migration (see db/migrations/): a role is a one-time,
-- credential-bearing administrative action, not a versioned schema change,
-- and dbmate's migration history is the wrong place to have ever stored a
-- plaintext password prompt. Same reasoning as db/seed_categories.sql being
-- a separate script from db/migrations/ -- run by hand, once per target,
-- not part of `dbmate up`. See docs/phase-5-dashboard.md.
--
-- SELECT-only, and only on the `marts` schema. `budget_dashboard` never
-- sees `staging` (thin pass-through views, not meant to be a stable
-- interface -- see docs/phase-3-transformation.md) or `public` (the raw
-- Phase 1/2 tables, including import_batches' lineage detail the dashboard
-- has no reason to read). This is the same "marts is the stable interface"
-- boundary Phase 3 already drew for dbt's own models; this script is what
-- makes Postgres itself enforce it for a second consumer.
--
-- Usage -- run against EACH target you want the dashboard to reach, with a
-- DIFFERENT password each time (local and Neon are different trust
-- boundaries, same as budget_admin's password already differs between
-- .env's POSTGRES_PASSWORD and the Neon project's own credential):
--
--   psql "$DATABASE_URL"      -v ON_ERROR_STOP=1 -v dashboard_password="a-strong-local-password"    -f db/grant_dashboard_readonly.sql
--   psql "$NEON_DATABASE_URL" -v ON_ERROR_STOP=1 -v dashboard_password="a-different-strong-password" -f db/grant_dashboard_readonly.sql
--
-- Safe to re-run: creates the role if missing, otherwise just rotates its
-- password and re-applies the grants below.
--
-- Whatever password you pick here is what goes into
-- dashboard/.streamlit/secrets.toml (see secrets.toml.example) -- never
-- into .env or dbt/profiles.yml, and never committed.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'budget_dashboard') THEN
        CREATE ROLE budget_dashboard WITH LOGIN PASSWORD :'dashboard_password';
    ELSE
        ALTER ROLE budget_dashboard WITH LOGIN PASSWORD :'dashboard_password';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE budget_pipeline TO budget_dashboard;
GRANT USAGE ON SCHEMA marts TO budget_dashboard;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO budget_dashboard;

-- Covers a mart added after this script has already run once -- `dbt build`
-- creates new tables in `marts` over time, and without this,
-- budget_dashboard would silently lose access to anything new until this
-- script was re-run by hand.
ALTER DEFAULT PRIVILEGES IN SCHEMA marts GRANT SELECT ON TABLES TO budget_dashboard;

-- Explicit, not just "a fresh role has no grants by default" -- states the
-- boundary in the script itself so a future reader sees the intent, not
-- just the absence of a grant.
REVOKE ALL ON SCHEMA staging FROM budget_dashboard;
REVOKE ALL ON SCHEMA public FROM budget_dashboard;
