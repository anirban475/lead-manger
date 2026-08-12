# Newspaper Radar — Jobdrive

A daily sweep of Indian newspaper classified recruitment ads. Newspaper job ads
carry what job boards strip out: the employer's own phone and email, printed so
candidates can apply direct.

Built and put into production 2026-08-12.

## Where the logic actually lives

**Not in this repo.** The scheduled task reads Outline directly, because a
scheduled session cannot load a skill body but can read a document. Change the
doc and the next run picks it up with no deploy.

| Thing | Where |
|---|---|
| Playbook, the source of truth | [Newspaper Radar Playbook](https://amatec.getoutline.com/doc/newspaper-radar-playbook-1V9PjBW6Uq) |
| Run state, reject keys | [Newspaper Radar State](https://amatec.getoutline.com/doc/newspaper-radar-state-8DWnxpUKhc) |
| Enterprise blocklist, shared with Naukri | [Enterprise Blocklist](https://amatec.getoutline.com/doc/enterprise-blocklist-kRHOVup0LR) |
| Scheduled task | `jd-lead-newspaper`, daily 08:30 local |
| Fetch workflow | n8n `aeWlxXTWGRHyGehZ`, "Newspaper Radar — Raw Ad Fetch" |
| MCP tool | `fetch_newspaper_ads` on the lead-scraper MCP, `zUbadDjZ9PfMR8av` |
| Script in this folder | `add_newspaper_mcp_tool.py`, one-off, already applied |

## The source

`https://www.ads2publish.com/published-ads/{slug}/recruitments`

Ads2Publish is the booking agency's published-ad archive. It republishes
classifieds as plain HTML text across **67 working publications**, including
every title whose own e-paper is paywalled. Each page carries exactly ten
classified ads plus up to two display ads, with a full category path under each.

Free, no login, updated daily. It is a rolling window, so a missed day is lost
permanently.

**Publisher e-papers were tried first and abandoned.** Twelve English Indian
titles, 2026-08-11: not one exposed a named job section, five were hard
paywalled, and ads sit inside pages labelled only "Advertisement" as images. A
vision agent asked to find them fabricated three job ads that did not exist.

## Four traps found in production. Read these.

**1. WebFetch silently drops ads.** It passes every page through a summarising
model. Ads2Publish numbers its ads sequentially and the extractions had gaps:
Deccan Chronicle jumped 2 to 4, Namasthe Telangana 4 to 7, Kannada Prabha
skipped 4, a dozen others the same. Those ads were fetched and thrown away before
anyone judged them, and the rolling window means they are gone. Fixed by moving
the fetch into n8n, which returns raw HTML with no model in the path. The
workflow now also emits `missingIndices` as a permanent gap detector.

**2. `update_workflow` strips credentials.** The lead-scraper MCP workflow
serves 12 tools, **ten of which carry credentials**. The n8n MCP's own
`get_workflow_details` returns those nodes with no credential IDs, so any
full-replace write built from that output silently removes authentication from
ten working tools. Verified, not theoretical. Edit that workflow in the UI or by
targeted database update, never by re-emitting it.

**3. A raw `active` column flip does not reload n8n.** Setting
`workflow_entity.active` false then true in Postgres does not touch n8n's
in-memory activation manager. During this build every acceptance check passed
while the new tool was absent from the live MCP endpoint. Use
`POST /api/v1/workflows/{id}/deactivate` then `/activate`, which take no request
body and so cannot strip anything.

**4. The first run's numbers were wrong, and one was invented.** It reported 58
saves and 640 ads while actually making 68 saves and fetching 614, and wrote the
same wrong pair into three places. Worse, its "331 park ads" was a **residual**,
computed as total minus everything else so the breakdown would balance. No park
tally was ever made. Decisions were nearly taken on a number that was never
observed. The playbook now carries counting rules: derive every aggregate from a
list, never report a bucket as a residual, and assert the header equals the sum
before writing.

None of this affected lead data. No company, role, email or phone was ever
invented. The failures were in counting and plumbing.

## Decisions worth not relitigating

**Business email outweighs every overload signal combined**, +20 against a +15
cap. Overload measures hiring pain, a business domain measures ability to pay,
and the second decides whether a lead is worth anyone's time. A firm still
applying through Gmail is usually too small to buy however desperate one ad
looks.

**Never filter on the company's home country.** The Naukri and LinkedIn radars
are India-only because a job board's location filter reflects where a company
operates. A newspaper ad is different: paying for a classified in an Indian
paper only makes sense if you are hiring in that paper's circulation area. The
ad placement is the proof, and it beats the registered address. A US BPO
advertising in the New Indian Express for a Tally accountant has an Indian back
office; a Dubai firm advertising in a Hyderabad Urdu daily is recruiting
Hyderabad candidates.

**Callability is enforced through `score`, not a new field.** The telecaller
cockpit sorts by `score DESC` and caps at 200 rows, so score already is the
mechanism. Park leads are clamped to 25 and sink below the cut rather than being
withheld. Nothing in the app changed.

**Warm only, no hot tier, no recurrence mechanism.** There is no `applyCount`
equivalent in a newspaper ad. Leads go straight to contact rather than ripening.

## What this source is worth

From the first production run, all figures counted rather than estimated:

| | |
|---|---|
| Publications | 67 working |
| Ads per full sweep | ~670 |
| Leads saved, day one | 68 |
| Carrying a phone | 81% |
| Carrying an email | 70% |
| **Business email domain** | **41%** |
| Cross-source duplicates against 220 existing leads | 0 |
| Government or education leakage | 0 |

The business-domain rate is the number that justified building this. The
estimate before starting was 8 to 12%.

## Known limits

- Ten ads per page, no pagination, no archive. Miss a day and it is gone.
- Individual ads carry no date, so first-seen is the only date signal.
- Apollo indexes roughly 40% of these companies. Not being in Apollo is itself
  evidence a company is too small to buy.
- Phone enrichment: Apollo returns named mobiles at roughly 75% on companies it
  knows, ~9 credits each. A website scrape hits about 17% and returns a
  switchboard. Use Apollo.
- Single point of failure on Ads2Publish. Cache raw pulls. The CareersWave PDF
  mirror is the fallback if it ever closes.

### Trap: flipping workflow_entity.active does not reload n8n

n8n holds active workflows in memory. Executing `UPDATE workflow_entity SET active = ...` directly in Postgres mutates the database row, but does not notify or reload the running n8n process.

The only way to trigger a live workflow reload from a script is via the n8n REST API deactivate/activate endpoint pair (`POST /api/v1/workflows/{id}/deactivate` followed by `POST /api/v1/workflows/{id}/activate`) on `http://localhost:5678`.

`add_newspaper_mcp_tool.py` retains the DB active-toggle solely as a degraded fallback when the REST API reload fails, exiting with status code `2` and printing `[RELOAD DEGRADED]` to `stderr`. An exit code of `2` indicates that while the database write succeeded, the in-memory workflow in n8n remains stale and must be manually reloaded via the n8n UI.

*(Note: The regression introduced in commit `2b18006` occurred because `urllib` was never imported. A bare `except` block inside the loop swallowed the resulting `NameError`, causing the script to report `[SUCCESS]` and exit `0` without ever reloading n8n or performing a fallback).*

