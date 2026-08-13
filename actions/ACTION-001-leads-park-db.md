# ACTION-001 — Create the `leads_park` database and `newspaper_ad_raw` table

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The newspaper radar reads roughly 650 classified ads a morning from Ads2Publish
and keeps about 50. The other 600 are discarded in memory and never written
anywhere. Ads2Publish is a rolling window, so a discarded ad cannot be fetched
again, ever.

Counted from `radar_runs` on 12 Aug 2026:

| Run date | Pulled | Saved | Dropped | Unaccounted |
|---|---|---|---|---|
| 2026-08-12 | 650 | 46 | 245 | 359 |
| 2026-08-12 | 614 | 68 | 546 | 0 |
| 2026-08-09 | 1065 | 72 | 988 | 5 |
| 2026-08-03 | 1988 | 37 | 61 | 1890 |
| 2026-07-19 | 2740 | 23 | 2705 | 12 |
| 2026-07-13 | 2358 | 30 | 2312 | 16 |

Two separate failures are visible here.

**One, roughly 6,900 records are gone and unrecoverable.** The scoring rules are
actively being revised, so ads rejected under today's rules may qualify under
next month's. There is no way to re-score history because history was not kept.

**Two, the counting does not reconcile.** On 2026-08-03, 1,988 were pulled,
37 saved and 61 dropped, leaving 1,890 unaccounted for. `dropped` is being
derived as an arithmetic residual rather than counted. This has already produced
one wrong public number in this project. Once every ad has a row, `dropped`
becomes `SELECT count(*) WHERE outcome = 'rejected'` and can no longer be
invented.

This brief creates the store only. Nothing writes to it yet. Wiring the radar to
populate it is deliberately a separate job, because that edit touches an n8n
workflow whose credentials are stripped by the API.

## Step 1 — report only, no changes

Read the current state and report:

1. `docker ps --format '{{.Names}}'` — confirm the Postgres container is named
   `shared-postgres`.
2. `docker exec shared-postgres psql -U admin -lqt | cut -d\| -f1` — list the
   databases and confirm whether `leads_park` already exists.
3. `docker exec shared-postgres psql -U admin -d leads -tAc "select version();"`
   — report the Postgres major version.
4. `docker exec shared-postgres psql -U admin -d leads -tAc "select current_user, session_user;"`
5. Confirm `/root/projects/lead-manger` exists, is a clean working copy, and
   report `git log --oneline -1`.

Report key names only where credentials are involved. Never print a value, not
even partially. Do not open, read or echo any `.env` file.

Stop after reporting. Do not write anything yet.

## Step 2 — create the migration file and apply it

Create `jd-lead-newspaper/sql/001_create_leads_park.sql` with exactly this
content:

```sql
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
```

Then apply it, in this order:

1. `docker exec shared-postgres psql -U admin -c "CREATE DATABASE leads_park;"`
2. `docker exec -i shared-postgres psql -U admin -d leads_park < jd-lead-newspaper/sql/001_create_leads_park.sql`

Requirements:

- The database is named exactly `leads_park`. Not `park`, not `leads-park`.
- The table lands in `leads_park`, **not** in `leads` and not in
  `marketing_analytics`.
- `CREATE DATABASE` runs on its own connection. It cannot run inside a
  transaction block, so do not wrap it or put it in the `.sql` file body.
- Non-goal: do not populate the table. It stays empty at the end of this task.
- Non-goal: do not create a `postgres_fdw` extension, foreign server, or user
  mapping. That needs a stored password and is out of scope here.

Then run both commands once and paste the real output. Not a summary of the
output.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/sql/001_create_leads_park.sql` to `main` with a
  message saying what it creates and why the ads cannot be re-fetched.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after Step 3 has been verified
independently:

- Merge to `main`.
- Delete this brief from `actions/`.
- Move anything learned that outlives the task into the repo README first.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do not modify the `leads` database or the `marketing_analytics` database in
  any way. No `ALTER`, no `DROP`, no `INSERT`, no `UPDATE`. This task is
  additive and creates one new database.
- Do not touch n8n workflow `aeWlxXTWGRHyGehZ` or the lead-scraper MCP workflow
  `zUbadDjZ9PfMR8av`. Editing those through the API strips their credentials,
  which has already broken this stack once.
- Do not restart, stop or reconfigure `shared-postgres`, n8n, or any other
  running service.
- Do not read, print, echo or partially reveal any password, token or `.env`
  value. Report key names only.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when all three hold:

1. `docker exec shared-postgres psql -U admin -d leads_park -c "\d newspaper_ad_raw"`
   runs, exits `0`, and lists 17 columns plus 5 indexes and 2 check constraints.
2. `docker exec shared-postgres psql -U admin -d leads_park -tAc "select count(*) from newspaper_ad_raw;"`
   returns `0` and exits `0`.
3. `docker exec shared-postgres psql -U admin -d leads -tAc "select count(*) from leads;"`
   returns the same number as it did in Step 1, proving the `leads` database was
   not touched.

And `jd-lead-newspaper/sql/001_create_leads_park.sql` is pushed to `main`.
