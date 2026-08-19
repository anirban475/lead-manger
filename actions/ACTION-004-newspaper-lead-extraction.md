# ACTION-004 — Newspaper lead extraction (measurement first, no production writes)

Owner: Anirban
Repo: anirban475/lead-manger
New file: `jd-lead-newspaper/sweep/extract.py`
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

The sweep now finds recruitment pages and stores their full-resolution OCR text
in `/root/newspaper_sweep/sweep.db`. Nothing turns that text into leads. This
builds that step.

It deliberately **writes nothing to the production `leads` database**. The job
of this task is to produce a measured answer to one question: how many
ICP-qualified leads does a newspaper page actually yield? Two findings below say
that number may be much lower than the raw contact counts suggest, and wiring a
pipeline into production before measuring would fill the telecaller cockpit with
junk.

### Finding 1: over half the contacts are matrimonial ads, not jobs

Measured across all 25 flagged pages holding 8 or more phone numbers:

**623 of 1,152 phone numbers, 54%, sit on matrimonial pages.**

The highest-scoring page in the entire project, Times of India Delhi 2026-08-02
page 14 with 242 phone numbers, is a matrimonial page. It reads
"SM4 Sanadhya Gaur Brahmin Boy 27, 176, BTech, wrkng in Japanese Automob. Comp.,
Good Salary" and "Alliance Invite". It passed the recruitment filter because
matrimonial ads are extremely phone-dense and use the words *working*, *salary*,
*qualified*, *REQ*, *seeks* and *MNC*.

Matrimonial pages are the single largest false-positive class and they are
concentrated on Sundays. Wednesday pages were clean.

### Finding 2: the sector mix is not the Jobdrive ICP

Keyword counts across the top flagged pages:

| Sector | Mentions |
|---|---|
| Education (school, teacher, PGT, TGT, principal, CBSE, coaching) | 269 |
| Medical (hospital, nurse, GNM, MBBS, RMO, pharmacist) | 96 |
| Industrial (pharma, chemical, manufacturing, production, warehouse) | 32 |

The Jobdrive ICP is small pharma, chemical and manufacturing firms with high
resume inflow. Education is on the existing hard-drop list, and coaching centres
have their own reject reason (`coaching_centre`). If most of what survives is
schools, the qualified yield could be near zero.

Do not assume either finding is fatal. Measure it.

## What already exists, and must be reused not rebuilt

- **`leads` table**: 23 columns, `company_key` is the primary key, upsert is
  `ON CONFLICT (company_key)` and deliberately never overwrites `status`.
- **`save_leads_bulk`** MCP tool on n8n workflow `zUbadDjZ9PfMR8av`. One argument
  `rows`, a JSON array of objects each with those 23 keys, all values as
  strings. `role_titles` is pipe-separated, `job_urls` comma-separated. Max 200
  per call.
- **`company_key` normalisation**, from the Naukri survivors workflow:
  ```js
  const norm = s => (s || '').toLowerCase()
    .replace(/\b(pvt|private|ltd|limited|llp|inc|co|company|industries|india)\b/gi, '')
    .replace(/[^a-z0-9]/g, '');
  ```
  Newspaper leads are identified by an `np` prefix on the key.
- **`newspaper_ad_raw`** table in the `leads_park` database,
  `sql/001_create_leads_park.sql`, keyed `ad_key`, with a reject-reason
  vocabulary: `enterprise, government, no_contact, size_gate, coaching_centre,
  dupe, low_score, other`.
- **Scoring point table**, from `jd-lead-scrapping/jobdrive-lead-radar-architecture.md`:
  size 10-100 stated +25, priority industry +20, high-volume role +15, 2+
  postings +15, phone or email present +10, no ATS +10. Business email is worth
  +20 against a +15 overload cap. 70+ hot, 50-69 warm, below 50 drop.

## Step 1 — report only, no changes

Report:

1. `\d leads` from the live database. Use
   `docker exec shared-postgres psql -U admin -d leads -c "\d leads"`. The repo
   has no DDL for this table, so the live schema is the only authority. Paste it
   verbatim.
2. Whether the `leads_park` database and `newspaper_ad_raw` table exist, and
   `\d newspaper_ad_raw` if so.
3. Row count in `page_scan` where `full_text is not null`.
4. Report credential and role NAMES only, never values.

Stop after reporting.

## Step 2 — build the extractor

Create `jd-lead-newspaper/sweep/extract.py`. Standard library plus `psycopg2` or
the existing `docker exec psql` pattern already used in this repo. **No LLM
calls in this step.** Rules only.

### 2a. Segment the page into ads

OCR loses the visual box boundaries, so ad segmentation cannot rely on layout.
Use **contact-anchored segmentation**: every phone number and email match is an
anchor; take a window of the surrounding text (tune it, start with 400
characters before and 100 after) as the candidate ad. Merge overlapping windows.

### 2b. Classify each candidate, and drop non-jobs

Classify as `matrimonial`, `property`, `recruitment` or `other`, by comparing
marker counts.

Matrimonial markers, case-insensitive: `sm4, pqm, alliance, bride, groom,
matrimonial, manglik, mglk, teetotaler, biodata, gotra, horoscope, kundli,
caste, brahmin, rajput, khatri, agarwal, jat, divorcee, never married,
wheatish, homely`, plus the pattern `seeks ... (girl|boy|bride|groom)` and
height patterns like `5'10"`.

Property markers: `bhk, sq ft, sqft, plot, flat, kothi, builder floor, for sale,
for rent, lease, freehold, possession`.

Recruitment markers: `vacancy, vacant, walk-in, resume, cv, apply, recruitment,
appointment, required, wanted, hiring, post of, interview, experience,
qualification`.

**Only `recruitment` proceeds.** Everything else is recorded with its
classification and dropped. This filter is the single most important part of
the task; get it wrong and the pipeline produces matrimonial contacts as sales
leads.

### 2c. Extract fields

From each surviving ad: `company_name`, `contact_phone`, `contact_email`,
`role_titles` (pipe-separated), `city`, and the raw ad text.

Company name is the hard one. Heuristic to start with: the longest run of
title-case or upper-case words within the window that is not a role title and
not a location. Expect this to be imperfect; report an accuracy estimate by
hand-checking 20 extractions rather than claiming it works.

### 2d. Apply the hard drops, and count each reason

Drop and tally: recruiters and staffing firms, enterprises, government, and
education or coaching. Use the reject vocabulary already defined:
`enterprise, government, no_contact, size_gate, coaching_centre, dupe,
low_score, other`.

Education needs its own explicit gate given finding 2: school, college, PGT,
TGT, PRT, NTT, principal, CBSE, coaching, tuition, academy, vidyalaya,
public school.

### 2e. Score, using the existing point table

Then bucket: 70+ hot, 50-69 warm, below 50 drop.

### 2f. Output a report, write nothing

Run over every `page_scan` row with `full_text is not null` and print:

- total candidate ads found
- counts by classification (matrimonial / property / recruitment / other)
- of the recruitment ads: counts by each drop reason
- how many survive to warm, and how many to hot
- **of the survivors, how many are the actual Jobdrive ICP** (pharma, chemical,
  nutra, food, manufacturing) versus education, medical or other
- 20 sample survivors printed in full: company, phone, email, roles, score

Write the whole result to `/root/newspaper_sweep/extract_report.json`.

### Explicit non-goals

**Do not write to the `leads` database. Do not call `save_leads` or
`save_leads_bulk`. Do not write to `leads_park`. Do not touch n8n.** This step
measures only. Wiring to production is a separate decision Anirban makes once he
sees the numbers.

## Step 3 — commit

Commit `jd-lead-newspaper/sweep/extract.py` and the report JSON. Remember
`.gitignore` line 31 is `*.py`, so `git add -f` is required or the commit
silently contains nothing. Paste `git show --stat HEAD`.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and `/root/newspaper_sweep/`.
- Do not restart, stop or reconfigure any pm2 process or the OCR service.
- Do not modify `sweep.py`, `app.py`, or anything under `ocr-service/`.
- Do not write to any Postgres database. Reads for Step 1 only.
- Do not print credential values.
- One step per reply. Finish a step, report, and wait.

## Acceptance

`python3 extract.py` runs to completion over all pages with `full_text`, writes
`/root/newspaper_sweep/extract_report.json`, and prints the classification
breakdown, the drop-reason tally, the survivor count and the ICP split. The
matrimonial classifier must correctly reject Times of India Delhi 2026-08-02
page 14, which holds 242 phone numbers and is entirely matrimonial. If that page
produces survivors, the filter has failed.
