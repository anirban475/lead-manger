# ACTION-014 — Leads routing columns and backfill

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Database: `leads` on container `shared-postgres`, user `admin`

This is Phase 0 (leads side) of the Lead Push to Mystrika build. Schema and
backfill only. **No behaviour changes anywhere.** The existing n8n sync
workflows keep running exactly as they are.

## Why this exists

A new push service will decide which lead goes into which Mystrika campaign.
It needs to route on four things: what we are selling (`offer`), why we are
writing now (`trigger_type`), how senior the person is (`buyer_level`), and
where they are (`country`).

**None of those four exist as columns today.** They are substrings buried
inside one free-text column, `leads.source_query`, in shapes like
`operations | US`, `newspaper | toi-mumbai` and
`operations (broad trigger set) | multi-geo`. Routing by string matching on
that column is exactly the fragility this build exists to remove.

Two related facts, both verified on 22 Aug 2026:

- `leads.origin` is `'scrape'` on 100% of rows. It is a dead column and carries
  no signal.
- The live Amatec sync filters `brand = 'amatec'`. The correct column is
  `eligible_brands`, a `text[]` that already exists with a check constraint and
  is currently unused. It makes no difference today because no lead is
  dual-eligible, but the moment one is, brand filtering sends it to the wrong
  place silently.

## Step 1 — report only, no changes

Read and report:

1. `\d leads` in full. Confirm whether `offer`, `trigger_type`, `buyer_level`
   and `country` already exist.
2. Every distinct `source_query` with a row count, for both brands, restricted
   to rows where `contact_email` is not null and not `''` or `'-'`.
3. Every distinct `contact_title` with a row count, for `brand='amatec'` only.
4. The row count of `leads` per brand, and how many have a usable
   `contact_email`.

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — write the migration and the backfill, run neither

Create two files. Do not apply them in this step.

### `sql/migrations/01_leads_routing_columns.sql`

```sql
ALTER TABLE leads
  ADD COLUMN IF NOT EXISTS offer        text,
  ADD COLUMN IF NOT EXISTS trigger_type text,
  ADD COLUMN IF NOT EXISTS buyer_level  text,
  ADD COLUMN IF NOT EXISTS country      char(2);

ALTER TABLE leads DROP CONSTRAINT IF EXISTS leads_buyer_level_chk;
ALTER TABLE leads ADD CONSTRAINT leads_buyer_level_chk
  CHECK (buyer_level IS NULL OR buyer_level IN ('owner','head','individual'));
```

Additive only. Do not drop, rename or retype any existing column. Do not touch
`origin`, `brand`, `mystrika_synced` or `eligible_brands`.

### `tools/backfill_leads_routing.py`

Requirements:

- **Dry run is the default.** It prints what it would set and changes nothing.
  A real write requires an explicit `--apply` flag.
- Parses `source_query` into `offer`, `trigger_type` and `country`.
- Derives `buyer_level` from `contact_title` by keyword:
  - `owner` — owner, founder, ceo, president, partner, proprietor, director
  - `head` — head, vp, vice president, manager, lead, chief
  - `individual` — everything else that is non-empty
- Prints a summary table: for each column, how many rows resolved, how many
  were left null, grouped by brand.
- Prints an **unparseable report**: every distinct `source_query` and every
  distinct `contact_title` it could not resolve, with counts. This is the most
  important output in the whole task.
- Exit 0 on success, 1 on any error. Never exit 0 after a partial write.

Non-goals: this script does not read or write `marketing_analytics`, does not
call any external API, and does not touch any table other than `leads`.

### Traps, and they are the point

These are easy to bulldoze past. Honouring them is how the rest of the run
earns trust.

1. **Never guess a country.** The bare value `CA` appears in `source_query`
   and is ambiguous between Canada and California. Leave `country` null for it
   and list it in the unparseable report. `Canada` spelled out is fine to map.
2. **`multi-geo` means no country.** Set `country` null. It affects 43 Amatec
   leads. **A null country must never be treated as a reason to exclude a
   lead.** This column is a send-window hint, not a filter.
3. **An unrecognised value is null plus a report line.** Never a guess, never a
   default, never a best-effort match. A visible gap is worth more than a
   plausible wrong value.

Then run the dry run once and paste the real output. Not a summary of it.

## Step 3 — apply, only after the Step 2 dry-run output is posted

1. Apply `sql/migrations/01_leads_routing_columns.sql`.
2. Prove it applied by running `\d leads` again and pasting the four new lines
   plus the constraint.
3. Run `tools/backfill_leads_routing.py --apply`.
4. Paste the real output, including the unparseable report.
5. Paste the result of this verification query:

```sql
SELECT brand,
       count(*) AS total,
       count(offer)        AS has_offer,
       count(trigger_type) AS has_trigger,
       count(buyer_level)  AS has_buyer_level,
       count(country)      AS has_country
FROM leads GROUP BY 1 ORDER BY 1;
```

## Step 4 — commit

Only after the Step 3 output is posted and looks right:

- Commit both files to `main` with a message saying what they do and why.
- Push to `origin`.
- Report the commit hash.

## Step 5 — merge and clean up

Claude does this, not Antigravity, and only after Step 4 has been verified
independently against GitHub and against the live schema.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- **Do not touch the `marketing_analytics` database at all.** That is a
  separate brief.
- Do not modify, deactivate, or even open any n8n workflow.
- Do not touch `telecaller-app/`, `jd-lead-newspaper/`, `jd-lead-scrapping/`
  or the `ocr-service`.
- Do not restart, stop or reconfigure any pm2 service.
- Do not drop or rename any existing column, in any table.
- Do not call the Mystrika API. Nothing in this task sends an email or touches
  a campaign.
- **One step per reply.** Finish a step, report, and wait. Do not batch.

## Acceptance

Done when:

1. `docker exec shared-postgres psql -U admin -d leads -c "\d leads"` shows
   `offer`, `trigger_type`, `buyer_level` and `country`, plus the
   `leads_buyer_level_chk` constraint.
2. `python3 tools/backfill_leads_routing.py` (no `--apply`) runs, prints the
   summary and the unparseable report, and exits `0`.
3. The verification query in Step 3 returns a row per brand with non-zero
   `has_offer` and `has_buyer_level`.
4. Both files are pushed to `main`.
