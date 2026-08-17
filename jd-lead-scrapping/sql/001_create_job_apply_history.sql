-- DDL for job_apply_history
-- Used to record seen apply counts for enriched Jobdrive job listings across radar runs

CREATE TABLE IF NOT EXISTS job_apply_history (
  id          BIGSERIAL PRIMARY KEY,
  job_id      TEXT NOT NULL,
  company_key TEXT,
  apply_count INTEGER NOT NULL,
  seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jah_job_seen ON job_apply_history (job_id, seen_at DESC);
