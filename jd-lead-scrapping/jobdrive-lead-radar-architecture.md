# Jobdrive Lead Radar — System Architecture

Reference file for the Jobdrive outbound lead engine. Read this before changing any part of the build so you know what depends on what.

**Owner:** Anirban
**Last updated:** 8 Jul 2026
**Status:** Scrape and store layer live and tested. Outreach layer not built yet.

---

## 1. What this system does

Finds companies in India that are hiring right now, scores them against the Jobdrive ICP, saves the good ones to a dedicated database, and hands the reachable ones to Bhratti for outreach. Every run learns from the last so query spend keeps improving.

**ICP:** hiring now, 10 to 100 employees, small or no HR team, high resume inflow. Priority industries pharma, chemical, nutraceutical, food, manufacturing. Gujarat first, the Ankleshwar, Vapi, Bharuch, Halol, Vadodara belt especially.

---

## 2. The pipeline end to end

```
Apify (kaix/indeed-scraper)
   -> run_indeed_scrape  [MCP tool]
      -> score + dedupe  [lead-radar skill, in chat]
         -> save_leads   [MCP tool] -> Postgres leads table
            -> hot leads  -> Slack to Bhratti -> status handed_off
            -> warm leads -> Apollo enrichment (TO BUILD) -> graduate to hot
   -> log_run + source_query feed the learning loop for the next run

OUTREACH LAYER (TO BUILD, post 1 Aug):
Postgres leads -> router -> Mystrika (email) + PayperWA (whatsapp)
   -> replies -> Chatwoot (one inbox) -> Slack alert to Bhratti
   -> opt out -> suppression table -> blocks both channels
```

Push stays fragmented across specialist tools. Catch is unified in Chatwoot. Postgres is the brain, everything else is an arm.

---

## 3. Components

| Layer | Tool | Host | Build vs buy |
|---|---|---|---|
| Scrape | Apify actor `kaix/indeed-scraper` (id `BIeK7ZcYUrdxDgOEQ`) | Apify cloud | Buy |
| Orchestration | n8n MCP server | self-hosted n8n | Build (thin) |
| Lead store | Postgres `leads` database | shared-postgres container | Reuse |
| Scoring + decisions | lead-radar skill | Claude | Build |
| Email outreach | Mystrika | SaaS | Buy (to wire) |
| WhatsApp outreach | PayperWA | SaaS | Buy (to wire) |
| Reply hub | Chatwoot | crm.amatec.in | Reuse (to wire) |
| Alerts + handoff | Slack | Slack | Reuse |

---

## 4. The MCP server

**Workflow:** Indeed Scraper MCP, id `zUbadDjZ9PfMR8av`
**Endpoint:** `n8n.amatec.in/mcp/lead-scraper`
**Trigger:** MCP Server Trigger, version 2
**URL:** https://n8n.amatec.in/workflow/zUbadDjZ9PfMR8av

### Tools (7)

| Tool | Type | Purpose |
|---|---|---|
| run_indeed_scrape | HTTP Request Tool | Scrape Indeed via Apify. Inputs keyword, location, maxItems, fromDays. Boolean titles supported. |
| run_actor | HTTP Request Tool | Generic Apify runner for trialing Naukri or Foundit actors. Inputs actorId, inputJson. |
| save_leads | Postgres Tool | Upsert one company into leads on company_key. Never overwrites in-play status. Carries source_query. |
| get_leads | Postgres Tool | Read leads filtered by status, or "all". Used to skip companies already in play. |
| log_run | Postgres Tool | Write a run to radar_runs. queries JSON plus totals plus next_plan. |
| get_run_history | Postgres Tool | Read past runs, the waste and credit side of learning. Input limit. |
| get_query_yield | Postgres Tool | Per-query conversion truth from leads, grouped by source_query. No input. |

### Apify call detail

- Endpoint: `POST https://api.apify.com/v2/actors/BIeK7ZcYUrdxDgOEQ/run-sync-get-dataset-items`
- Use `run-sync-get-dataset-items`, NOT `/runs`. Sync returns data in one call, async needs polling.
- Body built with `JSON.stringify` so boolean quotes in keyword do not break the JSON. Do not hand-template the body.
- country IN, sort date, searchMode basic, RESIDENTIAL proxy.
- Timeout 300000 ms. Keep maxItems 50 or under to stay inside the sync window.

---

## 5. Database

**Engine:** shared Postgres, container `shared-postgres`, on docker network `shared-network` (n8n reaches it as host `shared-postgres`, port 5432).

**Isolation:** dedicated database `leads` owned by dedicated role `leads_user`. PUBLIC revoked. No access to any other app database, and no other app can reach this one. This is the design guarantee, keep it. Never point these tools at another database, and never grant leads_user elsewhere.

**Credential in n8n:** named `Leads DB`. host shared-postgres, port 5432, db leads, user leads_user, SSL off.

### Table: leads (one row per company, keyed on company_key)

| Column | Type | Default | Notes |
|---|---|---|---|
| company_key | text | | PK, dedupe key |
| company_name | text | | |
| industry | text | | |
| size | text | | employee range |
| city | text | | |
| roles_count | int | 1 | postings by this company |
| role_titles | text[] | | |
| posted_date | date | | most recent posting |
| job_urls | text[] | | |
| contact_phone | text | | |
| contact_email | text | | |
| contact_source | text | | jd, website, apollo, or pending |
| company_website | text | | |
| score | int | | ICP score 0 to 100 |
| tier | text | | hot or warm |
| status | text | 'new' | pipeline stage |
| next_action | text | | |
| next_action_date | date | | |
| source_query | text | | "query \| location" that found it. Learning ground truth. |
| created_at | timestamptz | now() | |
| updated_at | timestamptz | now() | |

Indexes: PK company_key, plus idx on status, tier, source_query.

**status values:** new, enriched, queued, emailed, replied, hot, handed_off, won, lost, opted_out.

**Upsert rule (critical):** on conflict, save_leads updates roles_count, role_titles, posted_date, job_urls, score, tier and refreshes updated_at. It preserves status, contact, next_action, and source_query (via COALESCE). A re-scrape never resets an in-play lead to new. Tested and confirmed.

### Table: suppression

| Column | Type | Default |
|---|---|---|
| contact | text (PK) | phone or email |
| reason | text | |
| created_at | timestamptz | now() |

Router checks this before every send. One opt out kills both channels.

### Table: radar_runs (one row per run)

| Column | Type | Default |
|---|---|---|
| id | serial (PK) | |
| run_date | date | now() |
| queries | jsonb | one object per query: q, loc, items, hot, warm, dropped, credits |
| items_pulled | int | |
| hot | int | |
| warm | int | |
| dropped | int | |
| credits_est | numeric | |
| next_plan | text | |

---

## 6. The learning loop

Read at the top of a run, write at the bottom. All learning reads happen once, before any query fires, because the run's queries are planned as a batch.

**Read (plan):** get_query_yield for conversion per query, get_run_history for waste and credits per query, get_leads("all") to dedupe against in-play companies.

**Write (feed next run):** save_leads carries source_query on every company, log_run records per-query yield and the next plan.

Two sources by design. source_query in the leads table is the permanent conversion truth (what converted). radar_runs is the per-run snapshot that also holds what the table cannot, dropped counts and credits (what was wasted). Kill rule needs waste data, double-down rule needs conversion data, so both are kept. If ever forced to drop one, keep the column.

### Query decision rules

- Title is the axis, location broad. Rotate 3 to 4 titles per run.
- Kill: zero hot across two consecutive runs, retire the query.
- Double down: 2+ hot, raise its cap and add a sibling variant.
- Expand: hot yield per 100 items below 3 for two runs, trial a new board (Naukri or Foundit) via run_actor.
- Freshness: fromDays 7.

### Scoring (0 to 100, after hard drops)

Hard drop, never saved: recruiters and staffing firms, enterprises (1,000+, ENTERPRISE tier, corporate ATS apply URLs like oraclecloud, workday, successfactors, darwinbox, taleo), anything older than 7 days.

| Signal | Points |
|---|---|
| Size 10 to 100 stated | +25 (unknown + FREE tier +15) |
| Priority industry | +20 |
| High-volume role | +15 |
| 2+ concurrent postings | +15 |
| Phone or email in JD | +10 |
| Indeed easyApply, no ATS | +10 |
| FREE tier, no logo, few reviews | +5 |

70+ hot, 50 to 69 warm, below 50 drop. Gold signal: sloppy or AI-pasted JD, salary placeholders, "adjust before posting" leftovers means no HR function, the perfect buyer.

---

## 6b. Contact enrichment mechanism

Runs per lead, only after it is scored hot or warm. It is a cost-ordered cascade: each source is tried only if the cheaper one before it came back empty, so no effort or credit is spent that was not needed.

**Order of sources (cheapest first):**

1. **JD text** (free). Regex the scraped description for phone and email. Tag contact_source jd.
2. **Website / hiring post** (free). Scrape the company site and any hiring post for phone and email. Tag website. This is the step that won for Aneta, where Apollo had nothing.
3. **Apollo org search** (free, no credit). Returns HQ phone, domain, founded year. Tag apollo_org. Note: Apollo returns no employee count, so it does not validate the 10 to 100 size gate. Size stays on scrape and website signals.
4. **Apollo people search** (free) then **Apollo people enrichment** (paid, 1 credit). This branch is guarded twice and reached only for HOT leads: people search finds the HR person for free, then the reveal call spends one credit to unmask the name, direct mobile, and email. Tag apollo_person.

**The reveal gate.** Warm leads never reach the paid step, they stop at the free HQ phone from org search. The credit is spent only when the lead is hot AND greenlit to actually dial. This came from the live Apollo test where the HR person (Srushti, Senior GM HR at Umendra) was found free but her direct number was masked behind a paid reveal.

**Terminal states:** contact found (from any source) goes to the outreach queue; no Apollo record at all sets contact_source pending and routes to manual review.

**Guardrail:** any enriched lead still passes the suppression table check before any message is sent.

Full diagram: enrichment-flow.mermaid in the outputs folder.

---

## 7. Known gotchas (read before editing the MCP)

1. **Credential drop on republish.** Every `update_workflow` plus `publish_workflow` strips credentials from all HTTP and Postgres nodes. After any republish, manually reattach in the n8n UI: `Apify Token` on the two HTTP nodes, `Leads DB` on all five Postgres nodes. Auto-assign also tends to grab the wrong `telecaller_coaching` credential on Postgres nodes, so check each one.
2. **Stale MCP session.** After a republish the current Claude chat loses the tools. New tools only appear in a fresh chat session. Always test from a new chat.
3. **Boolean keyword.** save the body via JSON.stringify only. Hand-templated JSON breaks on the quotes inside boolean titles.
4. **Sync timeout.** run-sync-get-dataset-items caps at 300 s. Keep maxItems 50 or under, split larger pulls into more queries.

---

## 8. Credentials and secrets

- Apify token: stored in n8n credential `Apify Token` (Header Auth, `Authorization: Bearer ...`). Rotate periodically.
- Leads DB password: on the VPS, set on role leads_user. n8n credential `Leads DB`. Not stored in this file.
- Never put secrets in this document.

---

## 9. Team and handoff

- Hot leads: DM to Bhratti (Slack DM `D08977MGBTQ`), English only, ultra-short, signature " ..". After handoff, status moves to handed_off with a dated next_action.
- Bhratti works replies from Chatwoot once the outreach layer is live.
- Rule that stops leads slipping: a lead is not handled until it has a next_action with a date.

---

## 10. Build status and what is next

**Live and tested:** Apify scrape, MCP server with 7 tools, isolated leads database with 3 tables and indexes, upsert protection, first live batch (7 companies, 2 hot handed to Bhratti), the learning loop storage.

**To build, post 1 Aug (per CEO call, keep July hours on closing):**
1. Wire the enrichment cascade as an MCP tool set (see section 6b): JD, website, Apollo org search (free), Apollo people reveal (paid, hot only). Apollo MCP is connected and tested working.
2. Router: Postgres to Mystrika (email) and PayperWA (whatsapp), email first, WhatsApp gated behind a reply.
3. Reply capture into Chatwoot with Slack alert to Bhratti.
4. Opt out capture into the suppression table, checked before every send.
5. Stage-based campaign transfers driven by the status field, with replied leads pulled out of all sending instantly.

**Compliance flag:** PayperWA sits outside the official WhatsApp Business API. Keep volume low, personalize the first line, honor opt outs strictly, or risk the number being banned.

---

## 11. Related skills and files

- **lead-radar skill:** runs the scrape, scoring, save, and learning loop. Points at this MCP.
- **cto skill:** the technical decision seat, reads the System Map.
- **Amatec System Map (Outline):** the broader infra doc. This file is the deep dive for the lead radar specifically.
