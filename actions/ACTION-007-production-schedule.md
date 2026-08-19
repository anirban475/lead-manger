# ACTION-007 — Production schedule for the newspaper radar

Owner: Anirban
Repo: anirban475/lead-manger
Files: `jd-lead-newspaper/sweep/sweep.py` (edit), `jd-lead-newspaper/sweep/run_radar.sh` (new)
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

Every piece works and nothing runs on its own. `sweep.py` OCRs, `extract.py`
qualifies, `dedup.py` deduplicates and writes. This wires them into one command
and puts that command on a schedule.

It also corrects the edition list, which is currently the worst-performing set
we measured.

## Two decisions already made, do not relitigate

**Schedule: Wednesday and Sunday only.** Measured over 106 qualified leads
across 12 editions:

| Weekday | Edition-days | Leads | Leads per edition-day |
|---|---|---|---|
| Wednesday | 16 | 52 | 3.25 |
| Sunday | 20 | 44 | 2.20 |
| Tuesday | 8 | 6 | 0.75 |
| Friday | 8 | 2 | 0.25 |
| Saturday | 9 | 2 | 0.22 |
| Monday | 12 | 0 | 0.00 |
| Thursday | 8 | 0 | 0.00 |

Wednesday and Sunday are 96 of 106 leads, 91%. Monday and Thursday are hard
zeros across 20 edition-days combined.

**Plain VPS cron, not n8n.** The n8n OCR-node connection abort is still
unresolved, and the whole pilot ran over the SSH-direct path without a single
OCR failure. Do not put this in n8n.

## The edition list must change

Measured ICP leads per page, Sunday and Wednesday only, so the comparison is
fair:

| Edition | Pages | ICP | ICP/page | |
|---|---|---|---|---|
| TOI Mumbai | 52 | 6 | 0.115 | **add** |
| Daily Excelsior, Jammu | 36 | 4 | 0.111 | **add** |
| TOI Jaipur | 44 | 3 | 0.068 | add |
| TOI Delhi | 144 | 8 | 0.056 | keep |
| Mirror Mumbai | 116 | 6 | 0.052 | keep |
| TOI Bhopal | 42 | 2 | 0.048 | add |
| TOI Bangalore | 50 | 2 | 0.040 | add |
| HT Delhi | 121 | 1 | 0.008 | **drop** |
| TOI Ahmedabad | 91 | 0 | 0.000 | **drop** |

The current production four contain the two worst performers and neither of the
two best. HT Delhi spent 121 pages on one ICP lead; TOI Ahmedabad spent 91 on
none. Both samples are large enough to be signal.

Note TOI Bhopal is kept despite a mediocre 0.048 because it is by far the
densest edition measured at 12.67 phones per page, and the low conversion may be
an extraction problem rather than a source problem. Worth another month of data.

## Step 1 — report only

1. The current `EDITIONS` list in `sweep.py`, quoted verbatim.
2. The CLI arguments `sweep.py`, `extract.py` and `dedup.py` each accept.
3. Existing crontab for root: `crontab -l`.
4. Whether `/root/newspaper_sweep/` has a log rotation or cleanup in place.

Stop after reporting.

## Step 2 — update the edition list

Replace `EDITIONS` in `sweep.py` with these seven. All use
`https://d1h47qec6ptx2j.cloudfront.net`.

| key | paper | endpoint path | params |
|---|---|---|---|
| `toi-mumbai` | Times of India | `/toi/v2/download` | `citySlug=mumbai`, dmy |
| `toi-delhi` | Times of India | `/toi/v2/download` | `citySlug=delhi`, dmy |
| `toi-jaipur` | Times of India | `/toi/v2/download` | `citySlug=jaipur`, dmy |
| `toi-bhopal` | Times of India | `/toi/v2/download` | `citySlug=bhopal`, dmy |
| `toi-bangalore` | Times of India | `/toi/v2/download` | `citySlug=bangalore`, dmy |
| `mirror-mumbai` | Mirror | `/mirror/v2/download` | `citySlug=mumbai`, dmy |
| `excelsior-jammu` | Daily Excelsior | `/dailyexcelsior/v1/download` | `editionid=1`, `editiondate=DD/MM/YYYY` |

`dmy` means three separate zero-padded params `day`, `month`, `year`.

**Daily Excelsior needs a third date style.** It takes a single `editiondate` in
`DD/MM/YYYY`, lowercase, unlike HT's `editionDate` in `YYYY-MM-DD`. Add it as
`date_style: "ddmmyyyy_slash"` rather than special-casing it inline.

Remove `ht-delhi` and `toi-ahmedabad`.

## Step 3 — build `run_radar.sh`

A single entry point that runs the three stages in order and stops on failure.

```
sweep.py --days 1 --workers 4 --keyword-threshold 8
extract.py
dedup.py            # real write, not --dry-run
```

Requirements:

- Log to `/root/newspaper_sweep/logs/radar-YYYY-MM-DD.log`, one file per run.
- **Abort the chain if a stage exits non-zero.** Never run `dedup.py` against a
  half-populated sweep, because it would write a partial batch and mark those
  ads as seen, so the missing ones would never be retried.
- Guard against overlap with a lock file, so a slow run cannot be started twice.
  The 4-core box is already saturated by one run.
- Print a summary at the end: pages scanned, pages failed, qualified leads, new
  leads written, re-advertisements found.
- Delete logs older than 30 days.

## Step 4 — install the cron

```
30 6 * * 0,3 /root/projects/lead-manger/jd-lead-newspaper/sweep/run_radar.sh
```

Sunday and Wednesday at 06:30 server time. `--days 1` means it reads the
previous day's edition, which is published and stable by then.

Report `crontab -l` after installing.

## Step 5 — one supervised live run

Run `run_radar.sh` manually, once, start to finish. Paste the full summary and
report read back from the database:

- rows inserted into `leads`
- rows where `times_seen > 1`
- rows in `newspaper_ad_raw` by `outcome`

## Rules for this task

- Work only inside `/root/projects/lead-manger` and `/root/newspaper_sweep/`.
- Do not modify `extract.py` or `dedup.py`. Their logic is settled.
- Do not touch `ocr-service/` or restart any pm2 process.
- Do not put anything in n8n.
- `.gitignore` line 31 is `*.py`, so `git add -f` for any Python file.
- One step per reply. Finish a step, report, and wait.

## Acceptance

`crontab -l` shows the Sunday and Wednesday entry, a manual run completes all
three stages and writes leads, the lock file prevents a second concurrent run,
and a deliberately failed sweep stage stops the chain before `dedup.py` runs.
