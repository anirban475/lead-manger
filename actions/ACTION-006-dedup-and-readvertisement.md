# ACTION-006 — Dedup, re-advertisement signal, and writing to the leads database

Owner: Anirban
Repo: anirban475/lead-manger
Files: `jd-lead-newspaper/sweep/dedup.py` (new), `jd-lead-newspaper/sweep/extract.py` (extend)
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

Extraction works and produces qualified leads. Nothing yet writes them to the
`leads` database, and nothing deduplicates them. Both are needed before this
pipeline is worth running on a schedule.

**This is the first task in the newspaper radar that writes to production.**
Step 4 is a dry run and Step 5 is the real write, and they are separate on
purpose.

## The two things that must not be confused

Anirban's requirement: when a company already in the database appears again,
that means new openings and it should become a hot lead again, visibly.

That is correct, but only for a repeat on a **different date**. The coverage
work measured that Times of India syndicates the same classifieds package
across city editions, and the duplication rate swings between **1% and 48%**
depending on the week. On a high-syndication Sunday the same ad appears in
Mumbai, Pune, Bangalore, Ahmedabad and Hyderabad simultaneously.

| Situation | Meaning | Action |
|---|---|---|
| Same company, same edition date, different city editions | Syndication | Collapse silently, count once |
| Same company, a later edition date | Re-advertising, still hiring | **Re-activate as hot** |

Treating syndication as recurrence would mark almost every lead hot on a
syndication week and destroy the signal.

## What already exists and must be reused

- `leads`, 35 columns, `company_key` primary key, upsert `ON CONFLICT
  (company_key)`. Critically, the existing upsert **deliberately never
  overwrites `status`**, so a lead already in play with a telecaller is not
  reset by a rescrape. Preserve that.
- `save_leads_bulk` on n8n workflow `zUbadDjZ9PfMR8av`, argument `rows`, a JSON
  array of objects with 23 string keys, max 200 per call. `role_titles`
  pipe-separated, `job_urls` comma-separated.
- `newspaper_ad_raw` in the `leads_park` database, `ad_key` primary key, with
  `outcome` constrained to `saved|rejected|park` and `reject_reason` required
  when rejected. Vocabulary: `enterprise, government, no_contact, size_gate,
  coaching_centre, dupe, low_score, other`.
- `company_key` normalisation, already used by the Naukri radar:
  ```js
  const norm = s => (s || '').toLowerCase()
    .replace(/\b(pvt|private|ltd|limited|llp|inc|co|company|industries|india)\b/gi, '')
    .replace(/[^a-z0-9]/g, '');
  ```
  Newspaper keys carry an `np` prefix.
- The doctrine in `jd-lead-newspaper/README.md`: *"Callability is enforced
  through `score`, not a new field. The telecaller cockpit sorts by `score DESC`
  and caps at 200 rows."* So the re-advertisement signal must move `score`, or
  the telecaller will never see it.

Note that the same README currently states *"Warm only, no hot tier, no
recurrence mechanism."* Anirban has explicitly overturned that. Update that
paragraph as part of this task.

## Step 1 — report only, no changes

1. Confirm whether `leads` already has any column suitable for a sighting
   count. Report `\d leads` again and say explicitly whether `times_seen`,
   `last_seen_date` or similar exist.
2. Count existing rows in `leads` where `company_key LIKE 'np%'`.
3. Count rows in `newspaper_ad_raw`.
4. Report how `save_leads_bulk` is invoked from a script today, if at all, or
   state that no caller exists.

Report names only for credentials. Stop after reporting.

## Step 2 — schema, additive only

Add two nullable columns to `leads`. **Additive only. Do not alter or drop any
existing column, and do not touch the `leads_status_chk` constraint**, which
`memory.md` records as having broken production twice.

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS times_seen int DEFAULT 1;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_seen_date date;
```

Report the DDL you ran and the resulting `\d leads` for those two columns.

## Step 3 — build `dedup.py`

Three layers, in order.

**Layer 1, ad level.** `ad_key` = a stable hash of edition_key + edition_date +
page_no + normalised ad text. Skip anything already in `newspaper_ad_raw`. This
stops re-processing on a re-run.

**Layer 2, within a run, contact level.** Collapse ads sharing a phone number or
an email into one lead, across editions and dates inside the same batch. Keep
the highest-scoring instance, and union the role titles. **Key on contact, never
on company name** — name resolution is only 55% accurate, so name-based
collapsing would silently merge unrelated employers.

**Layer 3, against existing leads.** Look up `company_key`. Also look up by
`contact_phone` and `contact_email`, because the same employer can resolve to a
different name string between runs.

Then branch:

- **No match**: insert as new, `times_seen = 1`, `last_seen_date` = edition date.
- **Match, same `last_seen_date`**: syndication. Union role titles, do not
  increment `times_seen`, do not change score or tier.
- **Match, later date**: re-advertisement.
  - `times_seen = times_seen + 1`
  - `last_seen_date` = the new edition date
  - `score = min(100, score + 15)`
  - `tier = 'hot'`
  - append the new role titles
  - **do not touch `status`**

The +15 is deliberate: it matches the existing "2+ concurrent postings" signal
in the scoring table, since re-advertising is the newspaper equivalent of
concurrent postings.

## Step 4 — DRY RUN, no writes

Run the whole pipeline over everything currently in `sweep.db` and print:

- ads skipped at layer 1
- leads collapsed at layer 2, and how many were same-date syndication versus
  genuine duplicates
- layer 3 outcomes: new, syndication-merge, re-advertisement
- how many existing `leads` rows would be touched, listed by `company_key`
- the exact JSON that would be sent to `save_leads_bulk`, first 3 rows in full

**Write nothing.** Paste the real output.

## Step 5 — real write, only after Claude approves the dry run

Write via `save_leads_bulk`, batches of 200 or fewer, `brand` set to `jobdrive`
on every row, `contact_source` set to `newspaper`. Record every ad in
`newspaper_ad_raw` with its `outcome` and, when rejected, a `reject_reason` from
the existing vocabulary.

Then report actual counts read back from the database, not from your own
tallies: rows inserted, rows updated, rows where `times_seen > 1`.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and `/root/newspaper_sweep/`.
- Do not modify `sweep.py`, `app.py` or anything under `ocr-service/`.
- Do not restart any pm2 process.
- Do not modify the `leads_status_chk` constraint or any existing column.
- Do not run Step 5 until Claude has reviewed the Step 4 output and said so.
- `.gitignore` line 31 is `*.py`, so `git add -f`.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when: the dry run shows same-date syndication collapsing without
incrementing `times_seen`; a later-date repeat of the same company produces
`times_seen = 2`, `tier = 'hot'` and a +15 score; no existing lead has had its
`status` changed; and the counts reported in Step 5 are read back from the
database rather than accumulated in the script.
