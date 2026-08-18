# ACTION-002 — Newspaper sweep runner (recruitment-day map)

Owner: Anirban
Repo: anirban475/lead-manger
Target directory: `jd-lead-newspaper/sweep/`
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

Each Indian newspaper runs its appointments and classified recruitment section
on its own fixed weekday. We do not know which weekday, for any paper. Until we
do, a daily scrape wastes most of its work and a weekly scrape probably misses
the section entirely.

This runner answers that one question: for each edition, which weekday carries
the recruitment section, and on which page numbers.

It has to be resumable because it spans hours, and it has to discard page images
as it goes because the full run pulls several gigabytes of imagery that we have
no reason to keep.

Read `jd-lead-newspaper/README.md` first. It documents the verified endpoint
contracts and six traps that will otherwise cost you a rerun.

## The measured facts you must build around

**Downscaling destroys the contact signal.** Measured on TOI Delhi 2026-08-12
page 10, a confirmed appointments page, original 2748x4278:

| longest edge | secs | chars | phones | emails |
|---|---|---|---|---|
| 4278 (full) | 86 | 27,477 | 36 | 14 |
| 2748 | 32 | 24,757 | 9 | 3 |
| 2200 | 30 | 20,706 | 5 | 2 |
| 1800 | 12 | 9,056 | 1 | 1 |
| 1600 | 7 | 5,217 | 0 | 0 |

Phone numbers are the smallest type on the page. At 2200px, 86% of them are
gone. **Never extract contacts from a downscaled image.**

**Keywords do survive downscaling**, because section headers are large type. At
2200px the same page still yields 14 keyword hits including "E ARE HIRING",
"REQUIRED PURCHASER", "OTHER VACANCIES" and "Walk-in Interview".

**Keyword count discriminates, keyword presence does not.** Across all 32 pages
of that edition the median keyword count is 2. The three interesting pages
scored 24, 25 and 18. A boolean "contains the word required" matched 7 of the
first 9 pages, all false positives, because news prose contains "required",
"wanted" and "candidate".

So: **pass 1 at 2200px to find the section, pass 2 at full resolution to read
it.**

## Step 1 — report only, no changes

Report:

1. `nproc`, `free -g`, and `df -h /` on the VPS.
2. Whether `jd-lead-newspaper/sweep/` already exists.
3. The Python version Gunicorn runs under, and whether `requests` and `Pillow`
   are importable there.
4. Confirm the OCR service is answering: `curl -sS http://172.21.0.1:5050/health`
   and paste the real response.

Report key names only where credentials are involved. Never print a value.

Stop after reporting. Do not write anything yet.

## Step 2 — build the runner

Create `jd-lead-newspaper/sweep/sweep.py`. Single file, standard library plus
`requests` and `Pillow` only. No framework.

### Editions, hardcoded

```python
EDITIONS = [
  {"key":"ht-delhi",  "paper":"Hindustan Times", "city":"delhi",
   "url":"https://d1h47qec6ptx2j.cloudfront.net/hindustantimes/v2/download",
   "date_style":"iso",   "params":{"citySlug":"delhi"}},
  {"key":"toi-delhi", "paper":"Times of India",  "city":"delhi",
   "url":"https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
   "date_style":"dmy",   "params":{"citySlug":"delhi"}},
  {"key":"toi-ahmedabad","paper":"Times of India","city":"ahmedabad",
   "url":"https://d1h47qec6ptx2j.cloudfront.net/toi/v2/download",
   "date_style":"dmy",   "params":{"citySlug":"ahmedabad"}},
  {"key":"mirror-mumbai","paper":"Mirror","city":"mumbai",
   "url":"https://d1h47qec6ptx2j.cloudfront.net/mirror/v2/download",
   "date_style":"dmy",   "params":{"citySlug":"mumbai"}},
]
```

`date_style` `iso` sends `editionDate=YYYY-MM-DD`. `date_style` `dmy` sends
`day=DD&month=MM&year=YYYY`, zero-padded strings.

### Behaviour

1. **Dates newest first.** Given `--days N`, process today-1 backwards for N
   days. Newest first matters: if the run is stopped early, the most recent
   weeks are complete rather than a scattered half.

2. **Manifest.** GET the edition URL. Parse `data.htmlContent` and extract every
   `<img src="...">` in document order. **Count the img tags for the page count.
   Never use `totalPage`** — Mirror reports 120 while returning 20 images.
   Record the manifest result even when it returns zero images.

3. **Per page.** Download the image bare, no headers of any kind. Then:
   - **Pass 1**: downscale a copy to longest edge 2200, OCR with `lang=eng` via
     the OCR service at `http://172.21.0.1:5050/ocr?lang=eng`. Record
     `ocr_chars` and `keyword_count`.
   - **Pass 2, only if `keyword_count >= KEYWORD_THRESHOLD` (default 8)**: OCR
     the ORIGINAL image at full resolution, no downscale. Record
     `phone_count`, `email_count`, and store the full text.
   - Delete the image file immediately after, in a `finally`. Peak disk must
     stay under 100 MB regardless of run length.

4. **Keyword list**, case-insensitive, counting every occurrence not just pages
   that match:
   `vacancy, vacancies, vacant, required, requires, wanted, hiring, walk-in,
   walkin, recruitment, appointment, appointments, resume, curriculum vitae,
   situations vacant, apply now, send cv, candidates, applications invited,
   post of, salary`

5. **Regexes.** Phone `[6-9][0-9]{9}`, email
   `[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}`.

### Storage

SQLite at `/root/newspaper_sweep/sweep.db`. Two tables.

`manifest(edition_key, edition_date, weekday, page_count, status, error,
fetched_at)`, unique on `(edition_key, edition_date)`.

`page_scan(edition_key, paper, city, edition_date, weekday, page_no, image_url,
image_bytes, ocr_chars, keyword_count, phone_count, email_count, full_text,
pass1_seconds, pass2_seconds, status, error, scanned_at)`, unique on
`(edition_key, edition_date, page_no)`.

`status` must be one of `ok`, `timeout`, `download_failed`, `ocr_failed`.
**A timeout must never be recorded as a page with no keywords.** The OCR service
returns HTTP 504 with `"status": "timeout"` for this; treat any 504 as
`timeout`, and leave `keyword_count` NULL rather than 0.

### Resumability and concurrency

- On start, skip any `(edition_key, edition_date, page_no)` already present with
  `status='ok'`. Retry rows with any other status.
- 4 concurrent page workers, matching the 4 cores. Do not go higher; Tesseract
  runs with `OMP_THREAD_LIMIT=1` and is CPU-bound.
- 0.5 second delay between manifest requests. Be polite.
- Write each page row as it completes. Never batch to the end.

### CLI

`--days N` (default 56), `--editions a,b` (default all), `--max-edge` (default
2200), `--workers` (default 4), `--keyword-threshold` (default 8),
`--db` (default `/root/newspaper_sweep/sweep.db`).

### Logging

One line per page to stdout, flushed:
`<edition_key> <date> <weekday> p<NN> bytes=<n> kw=<n> chars=<n> [phones=<n> emails=<n>] <secs>s <status>`
and one summary line per edition-date.

### Explicit non-goals

No lead extraction, no scoring, no saving to the leads database, no dedup
against existing leads, no n8n, no cron. This runner produces the day-map data
and nothing else.

Then run it once, small, and paste the **real** output:

```
python3 sweep.py --days 1 --editions toi-delhi
```

## Step 3 — commit

Only after Step 2 output is posted and looks right:

- Commit `jd-lead-newspaper/sweep/sweep.py` to `main`, push, report the hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity.

## Rules for this task

- Work only inside `/root/projects/lead-manger`, plus creating
  `/root/newspaper_sweep/` for the database.
- Do not restart, stop or reconfigure the OCR service on 5050, or any pm2
  process.
- Do not edit anything under `jd-lead-newspaper/ocr-service/`,
  `jd-lead-newspaper/ocr-poc/` or `jd-lead-scrapping/`.
- Do not print environment variable values, tokens or credentials.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when `python3 sweep.py --days 1 --editions toi-delhi` completes, writes one
`manifest` row and one `page_scan` row per page into the database, every row has
a non-null `status`, no image files remain on disk afterwards, and the change is
pushed to `main`.
