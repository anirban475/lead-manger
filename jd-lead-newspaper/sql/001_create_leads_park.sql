-- 001_create_leads_park.sql
-- Park store for every newspaper classified the radar sees, kept or dropped.
-- Ads2Publish is a rolling window: an ad not stored on the day is gone forever.
-- Run the CREATE DATABASE line on its own, it cannot run inside a transaction.

-- psql -U admin -c "CREATE DATABASE leads_park;"

CREATE TABLE IF NOT EXISTS newspaper_ad_raw (
  ad_key          text        PRIMARY KEY,
  run_date        date        NOT NULL DEFAULT CURRENT_DATE,
  brand           text        NOT NULL DEFAULT 'jobdrive',
  publication     text,
  page_url        text,
  ad_index        integer,
  ad_text         text        NOT NULL,
  parsed_company  text,
  parsed_city     text,
  parsed_phone    text,
  parsed_email    text,
  parsed_roles    text[],
  outcome         text        NOT NULL,
  reject_reason   text,
  score           integer,
  company_key     text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT outcome_chk
    CHECK (outcome IN ('saved','rejected','park')),
  CONSTRAINT reject_reason_required
    CHECK (outcome <> 'rejected' OR reject_reason IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_np_raw_run_date
  ON newspaper_ad_raw (run_date DESC);
CREATE INDEX IF NOT EXISTS idx_np_raw_outcome
  ON newspaper_ad_raw (outcome);
CREATE INDEX IF NOT EXISTS idx_np_raw_reject
  ON newspaper_ad_raw (reject_reason) WHERE reject_reason IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_np_raw_email
  ON newspaper_ad_raw (lower(parsed_email)) WHERE parsed_email IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_np_raw_company_key
  ON newspaper_ad_raw (company_key) WHERE company_key IS NOT NULL;

COMMENT ON TABLE newspaper_ad_raw IS
  'Every classified the newspaper radar has seen. outcome=saved rows have a company_key into leads.leads. Source is a rolling window, so a row not written on the day cannot be recovered.';
COMMENT ON COLUMN newspaper_ad_raw.ad_text IS
  'Raw ad body. On this source the classified IS the job description, since employers advertising here rarely hold a separate JD document.';
COMMENT ON COLUMN newspaper_ad_raw.reject_reason IS
  'One of: enterprise, government, no_contact, size_gate, coaching_centre, dupe, low_score, other. Required when outcome=rejected.';
