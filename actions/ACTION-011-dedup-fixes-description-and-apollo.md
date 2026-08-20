# ACTION-011 — Multi-date dedup fix, job description, and Apollo enrichment

Owner: Anirban
Repo: anirban475/lead-manger
Files: `jd-lead-newspaper/sweep/dedup.py`, plus a new `enrich.py`
Working copy on VPS: `/root/projects/lead-manger`

**Confirm you are on `main` before committing.** A parallel session has left this
working copy on a feature branch before.

Three related changes, all touching the write path. Do them in order; part C
spends real money and comes last.

---

## Part A — Layer 2 must not collapse across dates

**This is a defect in the ACTION-006 brief, not in your implementation.** That
brief said Layer 2 should collapse duplicates "across editions and dates inside
the same batch". The "and dates" was wrong.

Collapsing across editions is correct, that is syndication. Collapsing across
**dates** destroys the re-advertisement signal, which is the whole point of
`times_seen`.

Evidence from the current database. 17 companies have saved ads on more than one
edition date, and `times_seen > 1` is zero across the entire table:

| company_key | distinct ad dates | range | times_seen |
|---|---|---|---|
| `np_exportdealinginchemicals` | 4 | 05 to 16 Aug | 1 |
| `np_gradientsecurity` | 3 | 02 to 12 Aug | 1 |
| `np_pinegroveschool` | 3 | 02 to 12 Aug | 1 |

Pinegrove's `last_seen_date` is stuck at 2026-08-04 despite advertising through
the 12th, so the date is wrong as well as the counter.

Role titles unioned correctly, so only the counter and date are affected.

### Fix

In Layer 2, key the collapse on **(contact, edition_date)** rather than contact
alone. Ads sharing a contact on the *same* date collapse as syndication. Ads
sharing a contact on *different* dates stay separate and flow into Layer 3,
where the re-advertisement branch handles them.

### Backfill repair

Recompute for existing `np%` leads from `newspaper_ad_raw`:

- `times_seen` = count of distinct `run_date` per `company_key` where
  `outcome='saved'`
- `last_seen_date` = max `run_date` for that `company_key`
- for any lead whose recomputed `times_seen` is 2 or more, set `tier='hot'`

**Do not touch `status`** on any row. A telecaller's work is never reset.
**Do not re-apply the +15 score bonus retroactively** — scores were computed
under the old logic and re-scoring historical rows would be guesswork. Only the
counter, the date and the tier.

Report how many rows changed and what the new `times_seen` distribution is.

---

## Part B — Job description and true city on the lead

The full ad text is already captured in `newspaper_ad_raw.ad_text`, 2,389 rows,
all populated. It is in the `leads_park` database, so the telecaller app cannot
join to it.

### Fix

Add to `leads`, additive only:

```sql
ALTER TABLE leads ADD COLUMN IF NOT EXISTS job_description text;
```

`dedup.py` writes the ad text into it alongside the lead. When several ads
collapse into one lead, join them with a blank line separator rather than
keeping only one, so a repeat advertiser accumulates their ads.

### Also fix `city`

`city` currently holds the **newspaper edition**, not where the job is. NIPS
Noida is tagged `jaipur` because the ad ran in the TOI Jaipur edition. That will
actively mislead a telecaller.

The ad text usually states the real location. Aryus Lube Tech reads
"…freshers may apply. **Navi Mumbai**. Send CV: sales@aryuslubetech.com" while
`city` says `mumbai`.

Extract a location from the ad text when one is present and use it for `city`.
Fall back to the edition city only when the ad states nothing. Add
`edition_city` as a separate column so the provenance is not lost.

Report how many leads got a city different from their edition.

---

## Part C — Apollo enrichment for email-only leads

Anirban has approved spending Apollo credits.

**45 of 101 leads carry an email but no phone**, so they never reach the
telecaller queue, which requires `contact_phone` with 8 or more digits.

### Step 1 for this part — report before building

Apollo credentials exist in n8n as credential `Apollo API`, type
`httpHeaderAuth`. The VPS Python has no direct key. Report:

1. Whether the Apollo API is reachable from the VPS at all, and by what route:
   directly with a key, or only through an n8n workflow that holds the
   credential.
2. Which existing n8n tools are Apollo-backed and what they accept.
3. Current Apollo credit balance if it can be read.

Report key **names** only. Never print a credential value.

### Then build `enrich.py`

Target set: `brand='jobdrive'`, `company_key LIKE 'np%'`, `contact_email` not
null, `contact_phone` null or under 8 digits.

For each, attempt to resolve a **direct phone number** for a decision maker at
that company. Write it to `contact_phone`, and set `contact_source` to
`apollo_person` or `apollo_org` to match the existing vocabulary.

**Money safety, all four are mandatory:**

- **Dry run by default.** Same pattern as `dedup.py`: `--write` must be explicit,
  and no flag means no spend. Do not repeat the `--dry-run` store_true bug.
- **Hard cap per run**, `--max-credits`, default 100. Stop when reached and say
  so, do not silently continue.
- **Never re-enrich.** Skip any lead already carrying `contact_source` starting
  `apollo`, even if the lookup returned nothing, or every run will re-buy the
  same failures. Record attempts that found nothing so they are not retried.
- **Log every call with its credit cost**, and report total spend read back from
  Apollo rather than estimated.

Expect a low hit rate and report it honestly. The repo's own note is that Apollo
indexes roughly 40% of these companies, and that absence from Apollo is itself
evidence a company is too small to buy.

Do **not** wire `enrich.py` into `run_radar.sh` in this task. It stays manual
until we have seen its real hit rate and cost.

---

## Rules for this task

- Work only inside `/root/projects/lead-manger` and `/root/newspaper_sweep/`.
- Do not modify `sweep.py`, `extract.py`, `run_radar.sh` or the OCR service.
- Additive schema changes only. Do not touch `leads_status_chk` or any existing
  column definition.
- Never change `status` on an existing lead.
- `.gitignore` line 31 is `*.py`, so `git add -f`.
- One part per reply. Finish A, report, wait. Then B. Then C.

## Acceptance

Part A: the 17 multi-date companies show `times_seen` equal to their distinct
date count, correct `last_seen_date`, and `tier='hot'`, with no `status` changed.
Part B: leads carry `job_description`, and at least some carry a `city` that
differs from `edition_city`.
Part C: a dry run reports the target count and estimated credits without
spending, and `--write` respects `--max-credits`.
