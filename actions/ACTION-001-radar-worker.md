# ACTION-001 — Radar worker: server-side scrape, filter and dedup for the Jobdrive lead radar

Owner: Anirban
Repo: `anirban475/lead-manger`
Working copy on VPS: `/root/projects/lead-manger`
Radar design workspace in this repo: `jd-lead-scrapping/`
Related n8n instance: `https://n8n.amatec.in`

---

## Why this exists

The weekly Jobdrive lead radar currently runs inside a Claude session that acts as a **courier**. It fires the Apify actor, polls it, pulls back 12 datasets of roughly 1 MB each, filters them, dedups them against Postgres, then writes the survivors back. Every one of those hops costs context, and almost none of it is judgement work.

Two measured costs from the 2026-08-16 run:

- Apify's `start_actor` and `get_run_status` return a large JSON blob (pricing tables, storage IDs, compute stats) to communicate one word: `SUCCEEDED`. Roughly 25 such calls per run, ~1.5–2K tokens each — **~40K tokens of pure noise**.
- Saving the qualified leads required emitting ~34 KB of row JSON across three `save_leads_bulk` calls, which is then echoed back in the result — **~20K tokens** to move data that was already on disk next to the agent.

The consequence is not just cost. Context spent on plumbing is context not spent on the decisions that actually need a model: spotting that "Envision Wind Power" is an MNC subsidiary, that "Simcon" is a testing lab rather than a volume-hiring manufacturer, or that four saved leads were dormant listings.

There is also a **half-finished piece already on the VPS**. The sub-workflow *"Naukri Two-Pass — List+Dedup (survivors)"* (`id 5GzoAqE8kCBm7A4N`, webhook `POST /webhook/naukri-survivors`) was built and smoke-tested on 2026-07-20 (exec 9070, ~13s: 120 list rows → 26 survivors). It was **never wired as an MCP tool**, so the scheduled agent cannot reach it — a webhook alone is unreachable from the agent's sandbox, where `curl` is blocked and outbound fetches are filtered by an egress proxy. It has sat unused ever since, and the 2026-08-16 run had to fall back to the slower method. This action finishes that job and extends it.

**Non-goal:** this is deliberately a thin slice. Scoring, the enterprise blocklist, the `get_company_size` gate and the actual `save_leads` writes stay with the agent. The radar is live and feeding outreach; a half-finished rewrite must not sit between Anirban and his leads.

---

## Background the builder needs

**Apify actor** `blackfalcondata~naukri-jobs-feed` (id `xYOP3UjaS8w38lWM7`), billed PAY_PER_EVENT:

| Event | Price |
|---|---|
| `standard-job-listing` (cheap list, `fetchDetails:false`) | $0.0005 / row |
| `enriched-job-posting` (`fetchDetails:true`) | $0.002 / row |
| `apify-actor-start` | $0.00005 |

Only the **enriched** tier returns `applyCount`, `industry` and `companyWebsite`. The **cheap** tier does return `companyName`, `jobId`, `consultant`, `footerLabel` and `location` — which is what makes the two-pass worth doing.

**Filter rules, measured on 880 rows from the 2026-08-16 run** (do not redesign these, implement them):

1. `postedBy: "Company"` at source, and drop any row with a truthy `consultant` field — removes recruiters.
2. **Live gate:** keep only `footerLabel` of 29 days or less. Drop `"30+ Days Ago"`.
3. **Volume floor:** keep only companies whose summed `applyCount` is >= 150.
4. **Velocity guard:** drop when the listing is older than 90 days AND `applyCount / days_since_created` < 3.

Why the live gate is not negotiable: `applyCount` is **cumulative and never resets when a listing is refreshed**. Of 102 companies clearing the 150-floor with no freshness gate, **88 were dormant zombies** — worst case `R. B. CONSTRUCTION COMPANY`, 15,942 cumulative applicants trickling in at ~1/day. Median applicants-per-day is 19.9 for live listings versus 1.1 for dormant ones, while median raw `applyCount` is 283 vs 293 — i.e. the raw count cannot separate them and the live gate can.

**Actor quirk, already verified:** on this actor `createdDate` tracks the **refresh**, not the original post. For every live row, `createdDate` age equals `footerLabel` exactly. This makes the velocity guard inert on this feed today — implement it anyway, because it is the only zombie filter available on the fallback actor `memo23~naukri-scraper` (id `EYXvM0o2lS7rYzgey`), which has no `footerLabel`.

**Database:** the same Postgres already behind the lead-scraper MCP. The `leads` table has a `brand` column; Jobdrive rows are `brand='jobdrive'` and dedup must filter on that. Do not alter `leads` or `radar_runs`.

---

## Step 1 — report only, no changes

Read the current state and report:

1. The n8n workflow `zUbadDjZ9PfMR8av` ("lead-scraper" MCP server): list its tool nodes by name, and state how many there are.
2. The sub-workflow `5GzoAqE8kCBm7A4N` ("Naukri Two-Pass — List+Dedup"): confirm it exists, is active, and paste its current node list.
3. How the n8n REST API is reachable from the VPS, and confirm that credentials for it exist. **Report key names only, never a value, not even partially.**
4. The Postgres connection used by the existing MCP tools: database name and how the credential is referenced. Again, **names only, never values**.
5. Confirm `actions/ACTION-001-radar-worker.md` is present at HEAD in the working copy, and list everything else currently in `actions/`.

Stop after reporting. Do not write anything yet.

---

## Step 2 — clear the stale brief

This brief was committed by Claude before dispatch, so there is nothing to save here. One cleanup instead:

- Delete `actions/ACTION-001-load-park-band-into-newspaper-ad-raw.md`. It is spent work from a finished job and Anirban has confirmed it should go.
- Commit and push. Report the commit hash.
- Touch nothing else in this step.

`actions/` should now contain only `ACTION-001-radar-worker.md`.

---

## Step 3 — build the worker sub-workflow

Extend the existing sub-workflow (or create a sibling — your call, state which and why) so that one call does the whole cheap-then-enrich cycle server-side.

**Input:** `keyword` (string), `location` (string), `max_results` (int, default 150), `min_apply_count` (int, default 150), `max_footer_days` (int, default 29).

**Behaviour:**

1. Apify pass 1, `fetchDetails:false`, `postedBy:"Company"`, `freshness:30`, `sortBy:"date"`.
2. Drop rows with truthy `consultant`; drop `footerLabel` older than `max_footer_days`.
3. Dedup against `leads` where `brand='jobdrive'`, matching on a normalised company name: lowercase, strip `pvt|private|ltd|limited|llp|inc|co|company|industries|india`, strip all non-alphanumerics.
4. Apify pass 2 on the surviving `jobIds` only, `fetchDetails:true`.
5. Apply the volume floor and the velocity guard.
6. Group by normalised company name, one object per company.

**Output — this is a contract, keep it compact.** Target under 4 KB for a typical 15-company result. One object per company:

```json
{
  "company_name": "...", "norm": "...", "city": "...", "industry": "...",
  "apply_count_total": 892, "roles_count": 4, "role_titles": ["..."],
  "job_ids": ["..."], "footer_days_min": 11, "created_age_days_min": 11,
  "velocity_max": 81.1, "company_website": "", "emails": [], "phones": [],
  "walkin": false
}
```

Plus one `meta` object: `{rows_listed, rows_enriched, dropped: {consultant, stale, dedup, below_floor, velocity}, apify_cost_estimate_usd}`.

Do **not** return raw job descriptions, HTML, `ambitionBox` blocks, skills arrays or any other actor field not listed above. Returning the full row defeats the entire purpose of this action.

**Error contract:** if Apify fails, times out, or returns zero rows, return HTTP 200 with `{"error": "<what failed>", "meta": {...}}`. **Never return an empty success that looks like "no leads this week"** — that is the one failure mode that would quietly kill the pipeline while appearing healthy.

Then run it once for `keyword: "QA Officer", location: "Gujarat"` and **paste the real output**. Not a summary of the output.

---

## Step 4 — delta logging table

Create **one new table**. Touch no existing table.

```sql
CREATE TABLE IF NOT EXISTS job_apply_history (
  id          BIGSERIAL PRIMARY KEY,
  job_id      TEXT NOT NULL,
  company_key TEXT,
  apply_count INTEGER NOT NULL,
  seen_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jah_job_seen ON job_apply_history (job_id, seen_at DESC);
```

Have the Step 3 worker insert one row per enriched job on every run. Insert-only; never update or delete.

Why: `applyCount` is cumulative, so it cannot distinguish a company that gained 300 applicants this week from one that gained 4 on top of a large historical total. Week-over-week delta can, and it is immune to the cumulative problem. This step only lays the baseline — the reading tool is deliberately out of scope.

Run it once, then paste the output of:

```sql
SELECT count(*) AS rows, count(DISTINCT job_id) AS jobs FROM job_apply_history;
```

---

## Step 5 — expose it as an MCP tool

Add a tool node named `list_survivors` to workflow `zUbadDjZ9PfMR8av`, wired into the MCP Server Trigger exactly like the existing `get_company_size` node, calling the Step 3 webhook with `keyword`, `location`, `max_results` built from `$fromAI`.

### The trap in this task — read twice

**Do NOT use the n8n MCP `update_workflow` tool to do this.** It is a full replace, and `get_workflow_details` does not expose the existing nodes' credential IDs. Re-emitting the workflow from code would strip the Apify and Postgres credentials off **all 10 currently working tools** and take the whole lead-scraper MCP server down.

Patch it through the n8n REST API (or the UI), reading the existing workflow **with** its credential IDs intact and adding one node. If you cannot do it without a full re-emit, **stop and report** rather than proceeding.

---

## Step 6 — regression check, the one that actually matters

After the patch, prove the existing tools still work. Call each of these through the MCP server and paste the real output:

1. `get_leads` with `status: "all"` — must return Jobdrive rows, not an auth error.
2. `get_company_size` with `name: "Soleos Energy", state: "Gujarat"` — must return a headcount.
3. `list_survivors` with `keyword: "QA Officer", location: "Gujarat"` — must return the Step 3 contract shape.

If 1 or 2 fails, the credentials were stripped: **stop immediately and report**. Do not attempt a fix that involves re-emitting the workflow.

---

## Step 7 — commit

Only after the Step 6 output is posted and looks right:

- Commit the worker definition, the SQL, and a short `jd-lead-scrapping/README-radar-worker.md` documenting the tool contract and the credential trap.
- Push to `origin`.
- Report the commit hash.

---

## Step 8 — merge and clean up

Claude does this, not Antigravity, and only after Step 6 and Step 7 output has been verified independently:

- Merge to `main`.
- Delete this brief from `actions/`.
- Move anything learned that outlives the task — a corrected figure, a new trap — into `jd-lead-scrapping/README-radar-worker.md` **before** deleting.

---

## Rules for this task

- Work only inside `/root/projects/lead-manger` and the two named n8n workflows. Touch nothing else on the VPS.
- Do not alter the `leads` or `radar_runs` tables in any way.
- Do not restart, stop or reconfigure the n8n service or the Slack listener.
- Do not print any credential value, not even partially. Key names only.
- Do not use the n8n MCP `update_workflow` tool on `zUbadDjZ9PfMR8av`. See Step 5.
- **One step per reply.** Finish a step, report, and wait. Do not batch.

---

## Acceptance

Done when:

1. `list_survivors` appears in the lead-scraper MCP tool list and, called with `keyword: "QA Officer", location: "Gujarat"`, returns a JSON array of company objects matching the Step 3 contract plus a `meta` object, in under 4 KB, exit 0.
2. Every returned company satisfies `apply_count_total >= 150` and `footer_days_min <= 29`.
3. `get_leads` and `get_company_size` still return real data through the MCP server after the patch.
4. `SELECT count(*) FROM job_apply_history;` returns a non-zero count.
5. A forced-failure run (e.g. a nonsense keyword yielding zero rows) returns an explicit `error` field rather than an empty success.
6. The work is pushed to `main` and this brief is deleted from `actions/`.
