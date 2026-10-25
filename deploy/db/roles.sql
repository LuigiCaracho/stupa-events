-- deploy/db/roles.sql: least-privilege DB roles (PLAN 11.1, M1-KONTRAKT 3).
-- Copied from STUPA-Workflow@93c33d6 deploy/db/roles.sql (adapted).
--
-- Run as superuser against DB `events`, two stages, idempotent (DO blocks, IF EXISTS):
--   stage 1 BEFORE `alembic upgrade head`: roles and default privileges (init-roles.sh at DB init)
--   stage 2 AFTER  `alembic upgrade head`: grants that need the tables (deploy.sh, smoke.sh)
-- Running the whole file at both points is safe: stage 2 skips tables that do not exist yet.
-- No passwords here: init-roles.sh sets them from the environment.

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_migrator') THEN
    CREATE ROLE events_migrator LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_app') THEN
    CREATE ROLE events_app LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_public') THEN
    CREATE ROLE events_public LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_subs') THEN
    CREATE ROLE events_subs LOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'events_audit_writer') THEN
    CREATE ROLE events_audit_writer NOLOGIN;
  END IF;
END $$;

ALTER ROLE events_public CONNECTION LIMIT 8;
ALTER ROLE events_public SET statement_timeout = '2s';
ALTER ROLE events_public SET idle_in_transaction_session_timeout = '5s';

-- events_subs holds the address key as a bind parameter: no statement or parameter text in the logs.
ALTER ROLE events_subs CONNECTION LIMIT 6;
ALTER ROLE events_subs SET statement_timeout = '3s';
ALTER ROLE events_subs SET idle_in_transaction_session_timeout = '5s';
ALTER ROLE events_subs SET log_parameter_max_length = 0;
ALTER ROLE events_subs SET log_parameter_max_length_on_error = 0;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE events TO events_app, events_migrator, events_public, events_subs;
GRANT CREATE ON DATABASE events TO events_migrator;
GRANT USAGE, CREATE ON SCHEMA public TO events_migrator;
GRANT USAGE ON SCHEMA public TO events_app, events_public, events_subs;

-- events_app never gets DELETE by default; stage 2 grants it per table. events_public gets nothing.
ALTER DEFAULT PRIVILEGES FOR ROLE events_migrator IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE ON TABLES TO events_app;
ALTER DEFAULT PRIVILEGES FOR ROLE events_migrator IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO events_app;

-- Stage 2. Append-only tables: INSERT and SELECT only (the triggers are the second layer).
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['audit_entry', 'event_revision', 'event_status_event', 'document_revision'] LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('REVOKE UPDATE, DELETE, TRUNCATE ON TABLE %I FROM events_app', t);
      EXECUTE format('GRANT INSERT, SELECT ON TABLE %I TO events_app', t);
    END IF;
  END LOOP;
END $$;

-- Stage 2. Tables the copied code deletes from. Authoritative list: backend/tests test_db_grants.py.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['auth_session', 'audit_verification', 'role_assignment', 'group_mapping', 'membership', 'editor_draft', 'checklist_item', 'notification', 'markdown_image', 'media_ref', 'geocode_cache'] LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('GRANT DELETE ON TABLE %I TO events_app', t);
    END IF;
  END LOOP;
END $$;

-- Stage 2. events_public reads the public views only.
DO $$
DECLARE r record;
BEGIN
  FOR r IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind IN ('r', 'v', 'm', 'p') LOOP
    EXECUTE format('REVOKE ALL ON TABLE %I FROM events_public', r.relname);
  END LOOP;
  FOR r IN SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'public' AND c.relkind = 'v' AND c.relname LIKE 'public\_%\_v' LOOP
    EXECUTE format('GRANT SELECT ON TABLE %I TO events_public', r.relname);
  END LOOP;
END $$;

-- Stage 2. Subscriptions: only events_subs writes them, and it never deletes (the privacy_*
-- functions do). events_app reads the interests and sees no other subscription table.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['subscriber', 'subscription_profile', 'outbox', 'listmonk_list', 'digest_run'] LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('REVOKE ALL ON TABLE %I FROM events_app', t);
      EXECUTE format('GRANT SELECT, INSERT, UPDATE ON TABLE %I TO events_subs', t);
    END IF;
  END LOOP;
  IF to_regclass('public.interest') IS NOT NULL THEN
    REVOKE ALL ON TABLE interest FROM events_app;
    GRANT SELECT ON TABLE interest TO events_app, events_subs;
  END IF;
  IF to_regclass('public.public_event_v') IS NOT NULL THEN
    GRANT SELECT ON TABLE public_event_v, public_category_v TO events_subs;
  END IF;
  IF to_regprocedure('public.privacy_erase_subscriber(uuid)') IS NOT NULL THEN
    GRANT EXECUTE ON FUNCTION privacy_erase_subscriber(uuid), privacy_purge_pending(timestamptz),
      privacy_anonymize_unsubscribed(timestamptz), privacy_purge_profiles(date),
      privacy_purge_outbox(timestamptz) TO events_subs;
  END IF;
END $$;
