# Lead Radar — Memory (verified truths)

Findings below were tested and confirmed on 2026-07-10. Treat them as ground truth for the Jobdrive lead radar. Anything not tested is marked as such.

## Scraper mechanics (Naukri, memo23~naukri-scraper, id EYXvM0o2lS7rYzgey)

- The actor hard caps at exactly 50 rows per run. Requested 200 returned 50. Four paginated startUrls returned 50. This is the actor's own output limit, not a wrapper or param artifact. Raising `maximumJobs` does nothing.
- Pagination cannot beat the cap. startUrls page URLs still return 50. Async plus dataset offset cannot fetch rows the actor never produced. Async only helps by removing the 5 minute sync timeout that killed the Hyderabad call, it does not add volume.
- Volume comes only from more slices, more title and belt combinations, each its own 50 row call.
- The `run-sync-get-dataset-items` endpoint has a hard 300 second (5 minute) cap that returns a 408, and it is an Apify API limit, not a plan setting. Upgrading free to Starter did NOT raise it (verified 2026-07-10). Starter only lowered cost and raised compute/concurrency. To pull more than fits in 300s, use async (start, poll, fetch dataset). blackfalcondata with fetchDetails at maxResults 150 + compact finishes inside 300s.

## Date fields

- Naukri `createdDate` is the original posting date, not the refresh date. Employers refresh old listings to stay live, so a job active today can carry a createdDate from months or years ago (seen 2020 to 2026 in one pull).
- `freshnessDays` filters on Naukri's own live or refreshed status, so it correctly returns active jobs. It does not filter by createdDate.
- Consequence: the old 7 to 14 day ripeness window measured on createdDate deleted active, flooded vacancies. On 2026-07-10 it dropped 1042 of 1052 rows and produced 2 hot, versus 2026-07-09 which produced 12 hot without strict ripeness. The window was the cause of the collapse, not the 50 cap.
- `footerLabel` (blackfalcondata only) is Naukri's displayed "posted X ago" line, captured as a string, and it reflects the REFRESH/repost recency, not createdDate. This is the truer freshness signal. Observed values (60-row test): "Today", then an exact day count for each day up to ~29 ("2 Days Ago", "7 Days Ago", "14 Days Ago", "21 Days Ago", "27 Days Ago", etc.), then everything older collapses into a single "30+ Days Ago" bucket (34 of 60 in that sample). A job with createdDate May 2025 still showed "30+ Days Ago", confirming it tracks refresh, not creation. It is granular 0 to 29 days, coarse beyond. To use numerically, parse the integer out: "Today" = 0, "14 Days Ago" = 14, "30+ Days Ago" = old/unknown-old. Use as the live gate: a specific recent count means actively refreshed and hot; "30+ Days Ago" with low applyCount velocity is a stale drip to drop. memo23 does not return this field.

## The right gate

- `applyCount` is present at scrape time and is high on active listings regardless of createdDate age. It is the real pressure signal.
- Gate on `applyCount` 150 or more. A clean baseline query kept 25 qualified ICP companies out of 50 rows. So the 50 cap is not the bottleneck once the query is clean and the gate is applyCount.
- Keep the size gate and pressure ratio behind the applyCount floor so a high apply enterprise still reads as popular, not drowning.
- `applyCount` is a running total since `createdDate` and is NOT reset when a listing is refreshed. Confirmed: a 2,040 day old active listing (Digidms) still carried 1,271 applies, and age and applyCount correlate +0.47. Only a true repost, which makes a new jobId, starts the count fresh.
- So raw applyCount mixes a live flood with a slow multi-year drip. Aneta drew 536 in 2 days, 268 a day. Expert had 1,987 over 728 days, 2.7 a day. Digidms 1,271 over about 5.6 years, 0.6 a day. Raw applyCount ranks the dead listings on top.
- Velocity guard: velocity = applyCount / days since createdDate (floor age at 1 day). Keep the 150 floor, but drop as a stale drip when the listing is older than 90 days AND velocity is under 3 applies per day. The actor exposes only createdDate, no refresh date, so velocity is a lower bound. The 90 day and 3-per-day thresholds are starting values, calibrate.

## Query construction

- `companyType: 1` returns employer posted jobs only. Confirmed all 50 rows came back consultant false. It removes recruiter and consultant noise at source.
- Use clean phrase queries only, for example `QA Officer`. Never use boolean NOT.
- Boolean NOT with OR grouping is valid syntax, the excluded companies do disappear. But any NOT clause, quoted or not, flips Naukri into loose keyword mode, so "Officer" starts matching bank, retail, hospital and facilities jobs. Qualified companies collapsed from 25 to 3 of 50 and enterprises and recruiters leaked back in. Net loss, do not use it.
- Exclude enterprises with the Enterprise Blocklist after the scrape, not with a source side NOT.

## Apollo

- The Apollo MCP tools for org enrich and people match or reveal carry a mandatory in-turn human confirmation guard. They cannot run unattended. Tiers 3 and 4 of the enrichment cascade will always stall in a scheduled routine. The playbook auto-spend instruction is defeated by this guard. Reveals need an attended pass, or the reveal must move off the Apollo MCP onto a direct API call in n8n.

## Size lookup risk

- `get_company_size` (EPFO via TheCompanyCheck) can wrong-match. "Sun Pharma" matched an unrelated 381 employee shell instead of the real 16,436 employee company. This is why the Enterprise Blocklist exists, to drop known giants before the size call.

## Where things live

- Outline collection "Lead Radar" holds two docs, the single source of truth.
  - Lead Radar Playbook, doc id 7723cebe-0335-4764-a715-ca53dc90333a
  - Enterprise Blocklist, doc id 46b5fc57-656f-459a-8799-31e36fbb33fa
- The lead-radar skill is a thin pointer to the playbook doc. Its doc id did not change when the doc moved into the collection, so the skill needed no edit.
- Blocklist self-grows: when get_company_size confirms a match over 500 employees, append that normalized name to the blocklist doc.

## Actor comparison (tested 2026-07-10, same QA Officer Gujarat query)

- The 50 cap is a memo23 problem, not a Naukri limit. Alternate actors return far more on one call: unfenced-group 120/120, blackfalcondata 60/60, muhammetakkurtt 60/60.
- **Chosen primary: blackfalcondata/naukri-jobs-feed (id xYOP3UjaS8w38lWM7, $0.50/1k).** No 50 cap, flat `applyCount` on every row with `fetchDetails:true`, reliable recruiter filter (`postedBy:"Company"`, verified via the `consultant` field, 60/60 came back consultant false), free-text location "Gujarat" works, and it returns `footerLabel`, Naukri's real "posted X ago" freshness (Today, N Days Ago, then a "30+ Days Ago" bucket) which memo23 strips. Also has incremental cross-run tracking (isRepost, changeType, firstSeenAt, lastSeenAt).
- blackfalcondata caveats: its built-in contact extraction underdelivered (contactPhone and contactEmail empty on 60/60), so keep the enrichment cascade. `applyCount` is still cumulative from `createdDate`. Newer actor (1.8K users, 1 review), so run in parallel with memo23 for one week before retiring memo23.
- unfenced-group ($0.78/1k) beats the cap and returns a real `publishDate` (0 to 30 days, respects daysOld), but returns NO applyCount, so it cannot drive our gate.
- muhammetakkurtt ($1/1k, 14K users) beats the cap and has applyCount, but only via `fetchDetails`, buried in a nested `jobDetails` object, with the same stale createdDate, and its location needs numeric Naukri city IDs (it rejected "Gujarat").
- Confirmed unsolvable by actor choice: no scraper computes applyCount from the real posting or refresh date. Naukri stores one cumulative applyCount tied to createdDate. Limitation 3 is a Naukri data fact.

## The 60s scrape ceiling is nginx, NOT the n8n node (verified 2026-07-13)

- The `run_actor` node in the "Indeed Scraper MCP" workflow (id zUbadDjZ9PfMR8av) ALREADY has `options.timeout: 300000` (300s). So the ~60s cap that limits fetchDetails:true to ~12 rows/call is NOT the node timeout. Raising the node timeout does nothing, it is already maxed.
- Real cause: the n8n nginx vhost `/etc/nginx/sites-available/n8n` has NO `proxy_read_timeout` directive, so it uses nginx's default of 60s. The node waits up to 300s for Apify, but nginx severs the MCP webhook response at 60s. That 60s is the ceiling.
- Immediate fix (reversible, no downtime): add `proxy_read_timeout 300s;` and `proxy_send_timeout 300s;` inside the `location /` block of that vhost, then `nginx -t && systemctl reload nginx`. Lifts 60s→300s, ~5x rows per fetchDetails call.
- Durable fix: switch run_actor from `run-sync-get-dataset-items` to async (POST /v2/acts/{id}/runs → poll /v2/actor-runs/{id} until SUCCEEDED → GET /v2/datasets/{id}/items). No long single call, so neither nginx nor Apify's own 300s sync cap can bite. This is the only path to the full 150/call design.
- Stale: run_actor's toolDescription still says "Primary use is Naukri (memo23~naukri-scraper)" (the 50-cap actor). Primary is now blackfalcondata. Update the description so the agent stops defaulting to the capped actor.

## Async scrape trio BUILT + VERIFIED live (2026-07-13, by Claude)

- Workflow zUbadDjZ9PfMR8av now has 11 tools. Added three httpRequestTool nodes wired to the MCP Server
  Trigger, all using the existing Apify httpHeaderAuth cred (id `YVb9zGOOAHmFZOZu` "Apify Indeed Scraper"):
  - **start_actor(actorId, inputJson)** — POST `https://api.apify.com/v2/acts/{actorId}/runs`, body=inputJson.
    Returns run JSON with `data.id` (runId) + `data.defaultDatasetId` in ~1s. Actor then runs on Apify.
  - **get_run_status(runId)** — GET `https://api.apify.com/v2/actor-runs/{runId}` → `data.status`
    (READY/RUNNING/SUCCEEDED/FAILED/ABORTED/TIMED-OUT) + `data.defaultDatasetId`.
  - **get_dataset_items(datasetId)** — GET `https://api.apify.com/v2/datasets/{datasetId}/items?clean=true&format=json` → rows.
  - `run_actor` kept as DEPRECATED fallback (description prefixed), stale "memo23 primary" text corrected to blackfalcondata.
- **Edit method that PRESERVES credentials (beats the republish-strips-creds gotcha):** `docker exec n8n
  n8n export:workflow --id=<id> --output=/tmp/x.json` → edit JSON (credential ids stay referenced) → `docker cp`
  back → `n8n import:workflow --input=` → `n8n update:workflow --id=<id> --active=true` → **`docker restart n8n`**
  (CLI active-toggle needs a process restart to register the webhook/MCP tools). Because the same cred ids
  (`YVb9zGOOAHmFZOZu` Apify, `X5J1B6V0TGfiw9x9` Leads Database) are re-imported verbatim, NOTHING is stripped.
  n8n uses `shared-postgres` db `n8n` user `n8n_user`. n8n v2.17.3, container name `n8n`.
- **n8n MCP endpoint speaks streamable HTTP.** POST `initialize` → capture `mcp-session-id` header → POST
  `notifications/initialized` (same header) → POST `tools/call`. Sessions persist across separate curl calls.
- **END-TO-END VERIFIED via the live tools (blackfalcondata xYOP3UjaS8w38lWM7, QA Officer / Gujarat):**
  - 150-row run, `fetchDetails:true`: start_actor 2s → run took **256s end to end** (06:49:46→06:54:02) →
    get_dataset_items 2s returned **all 150 rows**. Every individual call stayed ~1-2s. So a scrape far past
    the old 60s nginx ceiling completes with no long connection. The 60s wall is dead. nginx untouched.
  - **compact:true BUG CONFIRMED and FIXED in playbook.** The 150-row run used `compact:true` (old playbook
    input) → 0/150 rows had applyCount or footerLabel (only companyName/createdDate/description/location/
    salary/skills/title/jobId/portalUrl/experienceText). Re-ran 30 rows with `fetchDetails:true, compact:false`
    → **30/30 had applyCount** (1992, 814, 300, 791...) **and 30/30 had footerLabel** ("6 Days Ago",
    "30+ Days Ago") plus full contact/company fields. So `compact:true` strips the gate metric even with
    fetchDetails on. Playbook standard input changed to `compact:false`.
  - FAILED/ABORTED handling: get_run_status returns the raw Apify status string faithfully (saw READY,
    RUNNING, SUCCEEDED all correct), so the agent-side "stop on FAILED/ABORTED/TIMED-OUT" guard in the
    Playbook is sufficient. (A forced-abort round was not spent; status passthrough proven across states.)
  - Test cost ~$0.10 Apify. No save_leads called, so the leads DB was not touched by the test.

## PAY_PER_EVENT pricing + actor capabilities (verified 2026-07-13)

- **Pricing (from run pricingInfo, live):** `standard-job-listing` $0.0005, `enriched-job-posting` (fetchDetails) $0.002, `apify-actor-start` $0.00005. Enriched = $2/1k = 4x the old doc's $0.50/1k. Billing is per listing RETURNED; `maxResults` bills every enriched row whether it qualifies or not. Today: 2,358 enriched -> 46 kept, ~98% of spend on dropped rows.
- **fetchDetails:false cheap-tier test (30 rows, charged 30 standard + 1 start = $0.015):** applyCount NULL, industry NULL, companyWebsite NULL, extractedEmails/contactEmail NULL. Only populated cheap: companyName, `consultant` (30/30), `footerLabel` (30/30), title, location, jobId, isRepost/changeType/firstSeenAt/lastSeenAt. So a cheap pass CANNOT gate on applyCount, CANNOT filter by industry, CANNOT harvest emails. applyCount genuinely needs the $0.002 enriched tier (the old doc claim held).
- **Targeted enrichment EXISTS:** input schema has `jobIds[]` and `startUrls[]` (+ `ignoreUrlFailures`). So a two-pass works: cheap `fetchDetails:false` search -> filter/dedup on the cheap fields -> enrich ONLY survivor jobIds with `jobIds:[...]` + `fetchDetails:true`. This is the real cost cut (targeted enrichment), NOT applyCount-on-cheap-tier.
- **sortBy enum = only ['relevance','date'].** No applyCount sort, so you cannot front-load qualifiers; lowering maxResults drops random qualifiers. Lever 5's applyCount-sort is not possible.
- **Incremental fully supported:** `incremental`, `stateKey`, `skipReposts`, `emitUnchanged`, `emitExpired`, `notifyOnlyChanges`. Because billing is per RETURNED row, `incremental:true` + `stateKey` + `emitUnchanged:false` should bill only net-new/changed rows. VERIFY live (before/after chargedEventCounts) before relying on it.

## Incremental billing test — NEGATIVE (2026-07-13)

- Ran the same cheap query twice: incremental:true, stateKey:"inc-test-qaoff-guj-0713", emitUnchanged:false, fetchDetails:false, maxResults:30. Run A charged 30 standard-job-listing ($0.015). Run B (same stateKey, minutes later) ALSO charged 30, and its output was 30 rows all `changeType:"NEW"`. So the incremental STATE DID NOT PERSIST across two separate start_actor API runs, and billing was full both times.
- Conclusion: lever 2 (incremental, "~60-70% ongoing savings") does NOT work as we invoke it (ad-hoc API runs). State likely needs a persistent Actor task / named storage, not per-run default storage. And billing is per listing RETURNED, so a saving only appears if fewer rows are returned. Do NOT rely on incremental for cost.
- Pivot: get the recurrence saving on OUR side via the TWO-PASS + leads-DB dedup. Pass 1 cheap (`fetchDetails:false`, $0.0005/row) returns companyName+jobId+consultant+footerLabel; drop stale (footerLabel "30+ Days Ago") and drop companies already in the leads DB. Pass 2 enrich ONLY survivor jobIds (`jobIds:[...]` + `fetchDetails:true`, $0.002 each) for applyCount+industry+website. Cheap tier $0.0005 and jobIds[] input both confirmed. Cost math: single-pass 150 enriched = $0.30/call; two-pass = 150×$0.0005 ($0.075) + survivors×$0.002, so savings grow as the known-company set grows.

## Two-pass targeted enrichment VALIDATED end-to-end (2026-07-13)

- Pass 1 (cheap fetchDetails:false) gave 5 jobIds with applyCount NULL. Pass 2: `start_actor` with
  `{"jobIds":[5 ids],"fetchDetails:true,"compact":false}` → SUCCEEDED in 4s, charged EXACTLY
  `enriched-job-posting:5`, `standard-job-listing:0` ($0.01). So targeted enrichment bills ONLY the
  survivors, no re-search. Output = exactly those 5 jobIds, now with applyCount populated (1992, 821, 301,
  792, 173) and industry ("Pharmaceutical & Life Sciences"). The two-pass works and cuts enriched spend to
  survivors only.
- **JOIN GOTCHA:** the jobId-enrichment Pass 2 rows come back with `companyName` EMPTY (and companyWebsite
  null). Carry companyName/location/footerLabel from Pass 1 and JOIN Pass 2 onto Pass 1 by `jobId` to get
  the full record. applyCount + industry come from Pass 2; identity fields come from Pass 1.

## WebFetch email harvest verified (2026-07-13)

- WebFetch works through the proxy (curl was blocked). Tested 3 pending leads: Peakmed Lifecare ->
  `info@peakmedlifecare.com` (plain in footer). Sunrise Remedies -> email is Cloudflare-obfuscated
  (`/cdn-cgi/l/email-protection#<hash>`), plain regex misses it, but the hash decodes (XOR: first byte is
  the key, XOR each following byte) to `info@sunriseremedies.in`. Rubamin -> JS-rendered, WebFetch returned
  only meta/shell -> needs the Chrome fallback.
- **GOTCHA for the email cascade:** (1) decode Cloudflare `data-cfemail` / email-protection hashes, else
  real generic emails (info@/hr@) are missed. (2) JS-rendered sites return an empty shell to WebFetch ->
  fall back to Chrome tools (already in playbook). (3) plenty of SME sites carry `info@` generic addresses,
  so the email-pattern fallback (deprioritized as P2) is less necessary once cfemail decode is in.
- 57 leads currently sit at contact_source 'pending' (67 have no email); many have a website, so a
  backfill pass with WebFetch + cfemail decode should recover a good chunk.

## LinkedIn post source added + first run (2026-07-13)

- Best actor for the FEED (named contacts): `harvestapi~linkedin-post-search` (id `buIWk2uOUzTmcLsuB`),
  $0.002/post, NO cookies, run via start_actor. Input: searchQueries[] + maxPosts + postedLimit + sortBy:date
  + profileScraperMode:short. `short` returns author name + headline (`info`) + profile URL for free.
- Each post returns: content, author name, author headline, author LinkedIn profile URL, posted date, and
  OFTEN a direct hr@/phone written in the post body. This is the one source that hands you a named person.
- Added `contact_linkedin` (text) column to `leads` for the author profile URL. New rows use
  `contact_source='linkedin_post'`.
- First run: 8 hiring queries, 102 posts, $0.20. After dropping recruiters/aggregators ~27 were in-house;
  saved 10 clean company-email leads (naxcuure, asence, hofpharma, embio, sumanchem, amronchemicals,
  conceptshygiene, vitalcare, ajantapharma, eyewynk).
- **Gotchas:** hiring-keyword feeds are heavy with recruiters/aggregators (Fynd Talent, visiohr, Well Tech,
  PharmaCrew, PharmaStuff, tutorial/academy pages) — filter by author headline keywords. Company-name
  extraction from free post text is noisy (role phrases like "QC Chemist", "Walk-In Interview at X"); the
  safest company signal is the email domain, so only bulk-save leads that have a non-generic company email.
- LinkedIn JOBS board (separate): best scraper is `thirdwatch~linkedin-jobs-scraper` (id eF0s4U6RIMuwZzfs0),
  $0.001/result, no cookies, returns applicant_count + industry + salary — but the jobs board skews to big
  enterprises (PepsiCo/Reliance/Sun Pharma), the wrong end of the ICP, so the FEED/post source fits better.

## Not yet tested

- Whether a multi-term NOT would behave differently on Indeed (only Naukri was tested).
- blackfalcondata incremental mode across real weekly runs (changeType / firstSeenAt populate only after a baseline run).

## Telecaller Cockpit — deployment (verified 2026-07-10 by Claude, tester role)

- **Live**: `https://leads.amatec.in` responds — `/login` → 200, `/` → 307 redirect. Container
  `telecaller-app` runs on `127.0.0.1:3020` (nginx-proxied, Let's Encrypt TLS). Domain is
  `leads.amatec.in` (NOT the earlier-planned `calls.amatec.in`).
- **Postgres superuser role is `admin`** (not `postgres`) on the `shared-postgres` container, db `leads`.
- **Schema applied and confirmed**: tables `telecall_logs`, `lead_comments`, `app_users`; view
  `query_conversion`; `leads` denorm columns `last_disposition, last_called_at, call_count`; index
  `idx_telecall_logs_disposition`.
- **`telecall_logs` disposition CHECK = exactly 12 values**: no_answer, busy, call_dropped,
  invalid_number, connected, info_shared, interested, callback, meeting_booked, not_interested,
  converted, opted_out.
- **`telecaller_app` role is correctly least-privilege** (verified via information_schema): on `leads`
  it has SELECT + **column-level UPDATE only** on (status, next_action, next_action_date,
  last_disposition, last_called_at, call_count) — it CANNOT write score/tier/source_query. INSERT+SELECT
  on telecall_logs / lead_comments / suppression; SELECT on query_conversion; SELECT/INSERT/UPDATE on
  app_users. **No DELETE anywhere; no grant on `radar_runs`.** Isolation holds.
- **Seeded users**: `anirban@amatec.in` (Anirban Sinha) and `bhratti@amatec.in` (Bhratti Raval), role
  `caller`. Mrunal (the other telecaller in the legacy sheet) is NOT seeded.
- **Phone-gate works**: queue = active leads with ≥8 digits in `contact_phone`. On 2026-07-10, 10 of 22
  active leads are phone-visible (12 hidden as phone-less). The queue SQL executes cleanly on the live schema.
- `query_conversion` returns 13 rows; `telecall_logs` is empty (0) on fresh deploy.
## Telecaller Cockpit — UI functional QA (verified in-browser 2026-07-10, logged in as Bhratti)

- **PASS**: login (session persists across nav); queue renders 10 phone-gated leads sorted by score
  with apply_count / role_group / industry_label / "Ask for {name} ({title})" / follow-up badges;
  lead detail shows the 🚨 apply_count badge, "Ask for Kajal Desai · HR Head", size, all fields;
  **tap-to-dial** link is `href="tel:+919614961469"` (E.164, one-tap); **smart WhatsApp** serves the
  desktop variant `web.whatsapp.com/send?phone=` on macOS desktop; 12 dispositions render in the two
  groups (Couldn't connect / Talked); selecting `no_answer` reveals the follow-up-date field
  (default today) — NEEDS_FOLLOWUP works; **comment** writes + renders in the unified Activity Timeline
  ("💬 Comment by Bhratti Raval · time").
- **🔴 CRITICAL BUG — logging a call is fully broken.** The Log-call server action fails with Postgres
  `permission denied for table leads` (aclcheck_error). Cause: the column-level UPDATE grant on `leads`
  covers (status, next_action, next_action_date, last_disposition, last_called_at, call_count) but
  `actions/logCall.ts` also sets **`updated_at = now()`**, which is NOT granted. Postgres column-level
  UPDATE needs privilege on EVERY column in the SET list, so the whole UPDATE fails and the transaction
  rolls back → no telecall_logs row, no status change. Opt-out is broken for the same reason.
  **Fix**: add `updated_at` to the grant — `GRANT UPDATE (status,next_action,next_action_date,
  last_disposition,last_called_at,call_count,updated_at) ON leads TO telecaller_app;` (and in
  `deploy/schema.sql`). Verified 2026-07-10.
  **→ RESOLVED 2026-07-10**: `updated_at` added to the grant (confirmed live). Tester re-verified
  in-browser as Bhratti: `no_answer` logs correctly (telecall_logs + status→handed_off + next_action +
  follow-up date + call_count, renders in timeline); `opted_out` writes log + status→opted_out +
  suppression for BOTH the E.164 phone and email. Stats (`query_conversion`) + Follow-ups render.
  Artifacts deleted, production restored. **Functional QA GREEN.**
- **🟠 Deploy-hygiene — stale-bundle "Failed to find Server Action".** A browser tab opened before a
  redeploy hit `Failed to find Server Action "<id>"`; the action IDs change every rebuild. Fresh load /
  hard reload fixed it. **Fix**: set a stable `NEXT_SERVER_ACTIONS_ENCRYPTION_KEY` env in the container
  so action IDs survive rebuilds; interim, users hard-refresh after a deploy.
- **Note**: 503s were seen on `/queue`,`/stats`,`/followups` RSC prefetches during the action burst, but
  6 rapid direct `curl /queue` all returned 200 — transient, not a systemic rate-limit. Monitor.
- QA test artifacts (1 comment) were created then deleted; production data left clean (0/0, lead `new`).

## Telecaller Cockpit — Call Sheet redesign QA (verified in-browser 2026-07-10)

- **GREEN.** `/queue` + `/followups` now render a dense sticky-header `<table>` (CallSheet) ~15+
  leads/screen with a FilterBar (search + city/role/status + follow-up-due + HOT/WARM + Save-preset in
  localStorage). Row/[Log] opens a right slide-over `LeadPanel` over the dimmed list: apply_count,
  dial/copy phone (tel: "Call via softphone" + `web.whatsapp.com` desktop variant), 12 grouped
  dispositions, comment box, lazy-loaded Activity History, Lead Facts.
- **In-place writes work without navigation** (Antigravity added a `no_redirect` param to `logCall`):
  selecting a disposition → "Save Call Outcome" logs the call, updates the panel header + queue row to
  the new status, and the call appears in the timeline — queue stays put. "Post Comment" adds to the
  unified timeline (newest first) instantly. Both confirmed via psql, then test data deleted (prod clean).
- Programmatic `navigator.clipboard.readText()` hangs/times out under CDP — can't verify click-to-copy
  that way; rely on the visible "Copied ✓" flash + the confirmed tel:/WhatsApp links.

## Telecaller Cockpit — Update-5 QA (2026-07-14): Add/Edit PASS, Registered BLOCKED

- **Add Lead PASS** — "+ Add Lead" modal (supports comma-separated multi-numbers) creates
  `company_key='manual_'+uuid`, `origin='manual'`, `status='new'`, `source_query=NULL`; shows in queue
  with a "manual" tag, dialable, normal (bottom) sort. Verified via psql.
- **Edit contact PASS** — "✎ Edit" in the LeadPanel Contact Information section updates
  contact_phone/name/title, stamps `contact_source='manual'`, reflects instantly in panel + queue row.
- **🔴 CRITICAL — "Registered" (and won/lost/opted_out) BLOCKED by `leads_status_chk`.** Logging Registered
  fails: `new row for relation "leads" violates check constraint "leads_status_chk"`. A CHECK on
  `leads.status` was added on the SCRAPER/outreach side (sometime 2026-07-11..14) allowing only
  `new, handed_off, hot, replied, dnd, not_interested, contacted, qualified, disqualified` — it does NOT
  include the telecaller app's mapped statuses `won, lost, opted_out, registered`. So Converted→won,
  Not-interested→lost, Opted-out→opted_out, and Registered→registered ALL fail now. (On 2026-07-10 opt-out
  set status='opted_out' fine, so this constraint is new.) My Update-5 plan wrongly assumed leads.status was
  free-text — it is constrained. **Not yet hit by real users** (current statuses only new/hot/handed_off).
  **Fix (extend the constraint — non-breaking, both pipelines coexist):**
  `ALTER TABLE leads DROP CONSTRAINT leads_status_chk; ALTER TABLE leads ADD CONSTRAINT leads_status_chk
   CHECK (status IN ('new','handed_off','hot','replied','dnd','not_interested','contacted','qualified',
   'disqualified','won','lost','opted_out','registered'));` (confirm with the scraper/outreach owner first).
  **→ RESOLVED + tester-verified 2026-07-14.** The constraint was recreated to include
  `won,lost,opted_out,registered` (union of both pipelines). Tester re-logged "Registered" via the panel →
  `status='registered'` + `telecall_logs` row + lead stays in queue. Add Lead + Edit contact also PASS.
  **Update 5 QA GREEN.** Lesson: `leads.status` IS constrained by `leads_status_chk` (scraper-owned) — the
  telecaller app's STATUS_MAP (won/lost/opted_out/registered) must stay a subset of it. If either side adds
  a new status, update this constraint or writes fail.

## Telecaller Cockpit — Add-Lead modal centering fix (2026-07-14, Claude built+deployed directly)

- **Bug:** the "Add New Lead" modal ran off the bottom of the screen; the Cancel/Add Lead buttons were
  unreachable on shorter windows. Root cause: the modal centered with inline
  `transform: translate(-50%,-50%)` BUT also had `className="... animate-fade-in"`, and
  `@keyframes fadeIn { to { transform: translateY(0) } } ... forwards` **overrode the inline transform**
  (CSS animation transform wins over inline style), so the `-50%` vertical shift was lost — modal top sat
  at 50% and overflowed downward (measured `getBoundingClientRect`: top 344/bottom 856 in a 688px window).
- **Fix:** removed `animate-fade-in` from the modal's outer div (kept it off; error div still uses it) and
  added `maxHeight:'90vh'; overflowY:'auto'` for short screens. Now centered top 88 / bottom 600 in 688,
  Add-Lead button `btn.bottom=579 < winH` → reachable. `components/AddLeadForm.tsx`, edited on BOTH the
  local repo and `/opt/telecaller-app`, container rebuilt (`docker compose up -d --build`).
- **Gotcha:** never combine `transform`-based centering with a `forwards` animation whose keyframes set
  `transform` — the animation clobbers the centering. Center via a flex wrapper, or animate opacity only.
