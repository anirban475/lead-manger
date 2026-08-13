# ACTION-001 — Load the 2026-08-12 park band into `newspaper_ad_raw`

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

`jd-lead-newspaper/sql/README.md` says `newspaper_ad_raw` is empty by design and
nothing writes to it. That is still true, and the 2026-08-12 radar run proved the
cost: 650 classified ads were read, 132 became leads, and the raw text of the
rest was discarded in memory. Ads2Publish is a rolling window, so a discarded ad
cannot be fetched again once the window turns.

210 of those ads were classified **park** — real employers, scored too low to
reach the telecaller queue. They currently exist only as parsed rows in an n8n
Data Table called `park_lead`, which is the wrong home: it has no `ad_text`, so
the parse can never be redone, which is the exact failure the sql README argues
against.

This task moves those 210 into `leads_park.newspaper_ad_raw` **with their real
ad bodies re-fetched from source**, before the window turns and the bodies are
gone for good.

Scope is the park band only. The 245 rejected ads from the same run are a
separate, larger problem and are NOT in scope here.

## Step 1 — report only, no changes

Read and report:

1. Does database `leads_park` exist on `shared-postgres`, and does it contain
   table `newspaper_ad_raw`? Report the `\d newspaper_ad_raw` output and the
   current `SELECT count(*)`.
2. n8n stores its Data Tables in n8n's own Postgres. Find where the Data Table
   named `park_lead` (id `8cJ9wZhadXkvHTXi`) keeps its rows. Report the physical
   table name and `SELECT count(*)` for that Data Table.
3. Confirm `POST https://n8n.amatec.in/webhook/newspaper-ads` with body
   `{"slug":"times-of-india"}` still returns ads today. Paste the first ad object
   only.

Report database and key names only. Never print a credential value, not even
partially.

Stop after reporting. Do not write anything yet.

## Step 2 — build the loader

Create `jd-lead-newspaper/load_park_band.py`.

Behaviour:

- Read the 210 park rows out of the n8n `park_lead` Data Table.
- For each distinct publication in those rows, POST that slug to the
  `newspaper-ads` webhook once and hold the returned `ads[]`.
- Match a park row to an ad when the ad's `phone` (last 10 digits) or `email`
  (lowercased) equals the park row's `contact_phone` or `contact_email`.
- For each match, INSERT into `leads_park.newspaper_ad_raw`:
  - `ad_key` = first 16 hex of
    `sha1( lower(ad phone or email) + first 40 chars of the ad body, lowercased, whitespace collapsed )`
  - `ad_text` = the **full** ad body from the webhook, never truncated
  - `publication`, `page_url`, `ad_index` from the webhook response
  - `parsed_company`, `parsed_city`, `parsed_phone`, `parsed_email`,
    `parsed_roles` (as `text[]`), `score` from the park row
  - `outcome` = `'park'`, `reject_reason` = NULL, `company_key` = NULL,
    `brand` = `'jobdrive'`, `run_date` = `'2026-08-12'`
- `ON CONFLICT (ad_key) DO NOTHING`, so a re-run is safe.

Hard requirements:

- **Never synthesise, truncate or placeholder an `ad_text`.** If a park row has
  no matching ad in today's fetch, skip it and add it to a skipped list. A
  skipped row is a correct outcome, an invented one is not.
- Print at the end, on separate lines: `matched=<n>`, `skipped=<n>`,
  `inserted=<n>`, then every skipped company name.
- `matched + skipped` must equal 210. If it does not, exit 1.
- Exit 0 on a clean run, exit 1 on any database or HTTP error.
- Non-goal: do not touch the 245 rejected ads, and do not write any row with
  an `outcome` other than `park`.

Then run it once and paste the real output. Not a summary of the output.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/load_park_band.py` to `main` with a message saying
  what it loads and why the raw body matters.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after Step 3 is verified
independently from GitHub:

- Merge to `main`.
- Delete this brief from `actions/`.
- Move anything durable learned here into `jd-lead-newspaper/sql/README.md`
  before deleting, in particular the real match rate against the rolling window.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do **not** edit n8n workflows `aeWlxXTWGRHyGehZ` or `zUbadDjZ9PfMR8av`, by API,
  by UI or by database update. The sql README is explicit that the n8n API strips
  credentials from these. They are out of scope entirely.
- Do not restart, stop or reconfigure n8n, postgres or any container.
- Do not alter the schema of `newspaper_ad_raw`. If a column does not fit, stop
  and report rather than adding one.
- Do not delete the n8n `park_lead` Data Table. It is the source for this load.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when:

```
psql -d leads_park -c "SELECT count(*) FROM newspaper_ad_raw WHERE outcome='park';"
```

returns the same number the loader printed as `inserted`, the loader's
`matched + skipped` equals 210, the script exits 0, and the script is pushed to
`main`.
