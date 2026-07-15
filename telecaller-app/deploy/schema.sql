-- Telecaller Cockpit schema — additive, safe to re-run.
-- Apply as the leads owner / admin:  psql -U admin -d leads -f deploy/schema.sql
-- After this, set the role password separately:
--   ALTER ROLE telecaller_app LOGIN PASSWORD '<strong>';   (then put it in .env)

-- 1. Append-only call log
CREATE TABLE IF NOT EXISTS telecall_logs (
    id               bigserial PRIMARY KEY,
    company_key      text NOT NULL REFERENCES leads(company_key) ON DELETE CASCADE,
    called_at        timestamptz NOT NULL DEFAULT now(),
    caller           text NOT NULL,
    channel          text NOT NULL DEFAULT 'tel',
    disposition      text NOT NULL,
    reason           text,
    notes            text,
    follow_up_date   date,
    duration_seconds int,
    external_call_id text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT telecall_logs_disposition_chk CHECK (disposition IN
      ('no_answer','busy','call_dropped','invalid_number',
       'connected','info_shared','interested','callback',
       'meeting_booked','not_interested','converted','opted_out','registered'))
);
CREATE INDEX IF NOT EXISTS idx_telecall_logs_company_key ON telecall_logs(company_key);
CREATE INDEX IF NOT EXISTS idx_telecall_logs_called_at   ON telecall_logs(called_at);
CREATE INDEX IF NOT EXISTS idx_telecall_logs_disposition ON telecall_logs(disposition);

-- 2. Denormalized latest-call fields on leads (outside save_leads' upsert list)
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_disposition text;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_called_at   timestamptz;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS call_count       int NOT NULL DEFAULT 0;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS origin           text DEFAULT 'scrape';

-- 3. Per-query conversion signal (the feedback view the scraper reads)
CREATE OR REPLACE VIEW query_conversion AS
SELECT
    l.source_query,
    count(DISTINCT l.company_key)                               AS companies,
    count(DISTINCT l.company_key) FILTER (WHERE l.tier='hot')   AS hot_companies,
    round(avg(l.score),1)                                       AS avg_score,
    count(DISTINCT t.company_key)                               AS contacted_companies,
    count(t.id) FILTER (WHERE t.disposition='interested')       AS interested_calls,
    count(t.id) FILTER (WHERE t.disposition='converted')        AS converted_calls,
    count(t.id) FILTER (WHERE t.disposition='meeting_booked')   AS meeting_calls,
    count(t.id) FILTER (WHERE t.disposition='registered')       AS registered_calls,
    count(DISTINCT t.company_key) FILTER
      (WHERE t.disposition IN ('interested','converted','meeting_booked','registered')) AS positive_companies
FROM leads l
LEFT JOIN telecall_logs t ON t.company_key = l.company_key
WHERE l.source_query IS NOT NULL
GROUP BY l.source_query;

-- 3b. Freeform per-lead comments (separate from call outcomes)
CREATE TABLE IF NOT EXISTS lead_comments (
    id           bigserial PRIMARY KEY,
    company_key  text NOT NULL REFERENCES leads(company_key) ON DELETE CASCADE,
    author       text NOT NULL,
    body         text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lead_comments_company_key ON lead_comments(company_key);

-- 4. Auth users
CREATE TABLE IF NOT EXISTS app_users (
    id serial PRIMARY KEY,
    email text UNIQUE NOT NULL,
    password_hash text NOT NULL,
    display_name text,
    role text DEFAULT 'caller',
    created_at timestamptz DEFAULT now()
);

-- 5. Least-privilege app role (password set separately via ALTER ROLE)
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'telecaller_app') THEN
    CREATE ROLE telecaller_app LOGIN;
  END IF;
END $$;
GRANT CONNECT ON DATABASE leads TO telecaller_app;
GRANT USAGE  ON SCHEMA public   TO telecaller_app;
GRANT SELECT ON leads                       TO telecaller_app;
GRANT INSERT (company_key, company_name, contact_phone, contact_email, contact_name, contact_title, contact_source, city, status, origin, brand, created_at, updated_at) ON leads TO telecaller_app;
GRANT UPDATE (status, next_action, next_action_date, last_disposition, last_called_at, call_count, updated_at, contact_phone, contact_email, contact_name, contact_title, contact_source) ON leads TO telecaller_app;
GRANT SELECT, INSERT ON telecall_logs       TO telecaller_app;
GRANT USAGE, SELECT ON SEQUENCE telecall_logs_id_seq TO telecaller_app;
GRANT SELECT, INSERT ON lead_comments       TO telecaller_app;
GRANT USAGE, SELECT ON SEQUENCE lead_comments_id_seq TO telecaller_app;
GRANT SELECT, INSERT ON suppression         TO telecaller_app;
GRANT SELECT ON query_conversion            TO telecaller_app;
GRANT SELECT, INSERT, UPDATE ON app_users   TO telecaller_app;
GRANT USAGE, SELECT ON SEQUENCE app_users_id_seq TO telecaller_app;
-- Deliberately NO DELETE anywhere, NO access to radar_runs.

-- 6. Out-of-band constraints alignment (ensures statuses mapped in STATUS_MAP are permitted by scraper rules)
ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_status_chk;
ALTER TABLE leads ADD CONSTRAINT leads_status_chk CHECK (status IN
  ('new','handed_off','hot','replied','dnd','not_interested','contacted','qualified','disqualified',
   'won','lost','opted_out','registered'));

-- 7. Brand column default. `brand` is a scraper-owned NOT NULL column (added on the scraper/outreach
--    side, no default). The telecaller app's inserts (createLead / bulkCreateLeads) do not set `brand`,
--    so without a default every Add-Lead / CSV-import INSERT fails with a NOT NULL violation. All
--    current leads are 'jobdrive', which is the telecaller app's only brand, so default to it.
--    (Column is created by the scraper side; this ALTER assumes it already exists on the leads DB.)
ALTER TABLE leads ALTER COLUMN brand SET DEFAULT 'jobdrive';
