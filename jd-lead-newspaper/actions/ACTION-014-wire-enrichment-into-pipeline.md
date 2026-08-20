# ACTION-014 — Wire Apollo enrichment into the scheduled pipeline

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

`enrich.py` works, is committed, and has never once run on a schedule. The cron
pipeline `run_radar.sh` chains only three stages: `sweep.py`, `extract.py`,
`dedup.py --write`. Enrichment is not in the chain, so every scheduled run
since the cron was installed has written email-only leads into `leads` and left
them there.

This was deliberate. The ACTION-011 brief said, verbatim, "Do not wire
`enrich.py` into `run_radar.sh` in this task. It stays manual until we have
seen its real hit rate and cost." At that point the projection was roughly 9
credits per lead, extrapolated from the Naukri radar, which would have put a
full run near 650 credits. Holding it back until the real price was known was
correct.

The measured price turned out to be an order of magnitude lower. `people_search`
is free and only `reveal_emails` bills, so the real cost is 1 credit per match.
The one manual run spent 30 credits across 72 targets and recovered 23 phone
numbers, making 26 leads newly callable. Anirban has since removed the credit
cap entirely.

So the reason for keeping it manual is gone, and the cost of leaving it manual
is now visible in the data. The 2026-08-20 scheduled run wrote 23 leads, 14
with a phone and 9 with an email only. All 23 carry `contact_source =
'newspaper'`, which is the proof that no enrichment ran. Two of the nine are
hot tier and invisible to the telecaller purely for want of a phone number:

- Eonixtech, Bangalore, Technician, `info@eonixtech.com`, score 70
- Usoindia, South Delhi, Accountant, `hr@usoindia.org`, score 70

Those are leads we paid OCR and parsing effort to find, scored as hot, and then
could not call.

## Step 1 — report only, no changes

Read and report. Change nothing.

1. The exact current stage list in `jd-lead-newspaper/sweep/run_radar.sh`, in
   order, with the flags each stage is invoked with.
2. The full CLI surface of `enrich.py`. Every flag, its default, and
   specifically whether it has a dry-run/write split like `dedup.py` does, or
   whether it writes unconditionally.
3. How `enrich.py` currently selects its targets. State the actual query or
   filter. I need to know whether it self-limits to leads that have an email
   and no phone, or whether the caller is expected to scope it.
4. Its exit-code behaviour. What does it return when Apollo is unreachable,
   when zero targets match, and when the n8n MCP at
   `localhost:5678/mcp/amatec-radar` times out.
5. Whether it writes anything to stdout that a runner could parse for credits
   spent and phones resolved, or whether that would have to be added.

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify `jd-lead-newspaper/sweep/run_radar.sh` only.

Requirements:

- Add `enrich.py` as a fourth stage, positioned **after** `dedup.py --write`,
  never before. Ordering is not cosmetic. Enrichment must only ever touch leads
  that survived into the database, so a credit is never spent on a candidate
  that was about to be dropped.
- The stage runs inside the existing `flock` guard and writes to the same
  per-run log as the other three. No second lock, no second log file.
- The chain's existing `set -eo pipefail` discipline applies: a non-zero exit
  from enrichment fails the run visibly rather than being swallowed.
- The run summary line must report credits spent and phones resolved. A silent
  enrichment failure must be readable from the log alone, without SSH-ing in to
  reconstruct it. If `enrich.py` does not currently emit those two numbers in a
  parseable form, add that emission to `enrich.py` as part of this step.
- Non-goals, stated so they are not quietly attempted: do not add a credit cap,
  do not change the cron schedule, do not touch `sweep.py`, `extract.py` or
  `dedup.py`, do not alter the `leads` schema.

Then run the full chain once end to end and paste the real output. Not a
summary of the output. I want to see the four stage banners and the summary
line as they actually appear in the log.

## Step 3 — commit

Only after the Step 2 output is posted and looks right:

- Commit `run_radar.sh`, and `enrich.py` if it was touched, to `main` with a
  message saying what changed and why enrichment was previously excluded.
- Push to `origin`.
- Report the commit hash.

## Step 4 — merge and clean up

Claude does this, not Antigravity, and only after Step 3 has been verified
independently:

- Delete this brief from `actions/`.
- Record in the repo README that enrichment is now a scheduled stage, that it
  runs after dedup by design, and that the measured cost is 1 credit per match
  rather than the 9 originally projected. That corrected figure is the reason
  this change was safe, and it must outlive the brief.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do not edit `sweep.py`, `extract.py` or `dedup.py`.
- Do not modify the crontab.
- Do not restart, stop or reconfigure the OCR service on `172.21.0.1:5050`,
  `n8n`, or the `shared-postgres` container.
- Never touch the `leads_status_chk` constraint.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when `run_radar.sh` executes all four stages in order, the log's summary
line carries credits spent and phones resolved, a forced failure in the
enrichment stage causes the script to exit non-zero rather than report success,
and the change is pushed to `main`.
