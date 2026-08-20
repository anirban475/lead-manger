# ACTION-013 — Second role vocabulary pass, then re-extract the database

Owner: Anirban
Repo: anirban475/lead-manger
File: `jd-lead-newspaper/sweep/extract.py`, then a controlled re-run
Working copy on VPS: `/root/projects/lead-manger`. Confirm you are on `main`.

## Why this exists

Two gaps, both found by Anirban.

### Gap 1: the 67 `no_role` drops are still mostly parser misses

I dumped the actual 67 from the pipeline rather than sampling around them. Of 12
inspected, roughly 8 state a role plainly:

```
experienced Import Executive having expert knowledge of I...
female Sales/Marketing Exec. with good communication and computer skills
DISTRIBUTOR BUSINESS MANAGER  LOCATION: Delhi/NCR
EMPLOYEE NEEDED! Business Development Manager for Property Developer Company
CONSULTANT Business Development, required for a Plastic Moulding Mfg. Unit
Urgently Staff Required  Billing Staff- 2 no. (Salary+Pf etc)
Exec, DJ, GRE for Restaurant/lounge at Radisson Paschim Vihar
NEHRU INTERNATIONAL PUBLIC SCHOOL ... seeking applications for the posts of
```

Genuinely role-less, for calibration, so you know what the floor looks like: a
Times of India self-promo pointing at `ads.timesofindia.com`, a governance
notice about directors' remuneration, and two truncated fragments.

### Gap 2: the database was never re-extracted

The segmentation improvements are committed but every lead in `leads` was
extracted with the **old** logic. The DB holds 405 `np%` leads and 192 saved raw
ads, while the improved extraction yields 218 survivors. Those 218 exist only in
a scratch report at `/root/newspaper_sweep/seg_report.json`.

## Step 1 — report only

1. The current `ROLE_PATTERNS` list, quoted in full.
2. Whether slash-combined titles such as `Sales/Marketing Exec` can match today,
   and how the splitter handles `/`.
3. Whether any generic `<word> Staff` pattern exists.
4. Row counts: `leads` where `company_key LIKE 'np%'`, and `newspaper_ad_raw` by
   `outcome`.

Stop after reporting.

## Step 2 — vocabulary pass

Add, at minimum:

**Business and commercial**: Business Development Manager, Business Development
Executive, Business Development Consultant, BD Manager, BD Executive,
Distributor Business Manager, Area Business Manager, Territory Manager,
Relationship Manager, Branch Manager, Billing Staff, Billing Executive,
Import Executive, Export Executive, Import/Export Executive, Merchandiser,
Procurement Executive, Consultant.

**Hospitality and service**: DJ, Steward, Captain, Bartender, Chef, Commis,
Housekeeping Supervisor, Front Office Executive, Guest Relations Executive, GRE.

**Generic staff pattern**: match `<qualifier> Staff` where the qualifier is a
word, for example `Billing Staff`, `Nursing Staff`, `Female Staff`, `Office
Staff`, `Sales Staff`. Do not match a bare `Staff` alone, since "staff required"
with no qualifier carries no information.

**Slash-combined titles**: `Sales/Marketing Exec` should yield both Sales
Executive and Marketing Executive, not zero. Split on `/` inside a candidate
title and match each side, then expand a trailing shared suffix such as `Exec`
across both.

**Trailing role lists**: `seeking applications for the posts of` followed by a
list is a strong role cue. Where the list is cut off by the window, still record
what is present rather than returning nothing.

### Non-goals

Do not change segmentation, it is settled at zero false merges. Do not change
the classifiers. Do not enable `--drop-no-role`.

### Report

Re-run over `sweep.db` and give before and after for: candidate ads, ads
resolving at least one role, `no_role` count, survivors, hot, ICP. Then **dump
the remaining `no_role` ads in full** and state honestly how many still contain
a visible role. The target is that the remainder are genuinely role-less, not
that the number is merely smaller.

## Step 3 — re-extract the database, dry run first

The improved logic must now be applied to real leads.

**The risk to prove before writing:** `ad_key` is a hash of the ad text.
Better segmentation changes the boundaries, so ad_keys change, and Layer 1 will
treat every segment as new. Layer 2 and 3 dedup on contact *should* collapse
them onto existing leads rather than duplicating, but that is an assumption
until measured.

Run `dedup.py` **dry** and report:

- how many segments match an existing lead by contact
- how many would be inserted as genuinely new
- **the projected `np%` lead count after the write**

If that projected count jumps materially above 405, dedup is not collapsing onto
existing leads and you must stop and report rather than write. A duplicated lead
book is far worse than a stale one.

Only once the dry run looks right, run with `--write` and report actual counts
read back from the database.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and `/root/newspaper_sweep/`.
- Do not modify `sweep.py`, `run_radar.sh`, `enrich.py` or the OCR service.
- Never change `status` on an existing lead.
- Do not run Step 3's write until the dry run has been reported and approved.
- `.gitignore` line 31 is `*.py`, so `git add -f`. Commit **and push**.
- One step per reply.

## Acceptance

The remaining `no_role` ads are genuinely role-less on inspection, the dry run
shows existing leads being updated rather than duplicated, and the post-write
`np%` count is consistent with that.
