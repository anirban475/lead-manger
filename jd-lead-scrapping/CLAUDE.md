# Jobdrive Lead Radar & Cockpit — Agent Guide (CLAUDE.md)

This file serves as the workspace guide and handoff log between Claude and Antigravity. Both agents must read this first at the start of a session and update the handoff section before finishing.

---

## ⚡ Agent Triggers / Commands
- **`do handoff`**: When the user says this, the active agent must immediately write a **Hot Handoff** summary to the "Current Focus & Handoff State" section of this file (detailing exact files edited, current compiler/runtime errors, and the immediate next step) and stop the session.
- **`handup`**: When the user says this, the active agent must immediately read this `CLAUDE.md` file, summarize the changes and achievements from the previous session, outline the current system state, and report that it is ready to pick up execution from the handoff checklist.

---

## 🧠 Memory Discipline
- **Record concrete facts as you find them.** In any session, whenever a concrete verified fact is recovered (a tested limit, a confirmed API or tool behaviour, a data truth, or a gotcha proven by evidence), append it to `memory.md` in this project folder before the session ends. Save only what is established by test or direct evidence, and mark anything unverified as such. Both `memory.md` and this `CLAUDE.md` are read at the start of every session.

---

## 📂 Project Directory Map
- **Lead Scraper & System Architecture (This Workspace)**:
  `file:///Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Claude/Projects/Workflow/Jd Lead Scrapping/JD%20Lead%20Scrapping/`
- **Telecaller Cockpit Next.js App**:
  `file:///Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Local%20Routines/telecaller-app/`
- **Telecaller Coaching & Slack Bot System**:
  `file:///Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Claude/Projects/Workflow/Telecaller%20Couch/`

---

## 🛠️ Common Commands

### Telecaller App (Next.js)
*Run these inside the `/Local Routines/telecaller-app/` directory:*
- **Start Dev Server**: `npm run dev`
- **Build Project**: `npm run build`
- **Start Production**: `npm start`
- **Run Linter**: `npm run lint`

---

## 📍 Current Focus & Handoff State

### 🎯 Active Objective
- **TESTER (Claude): run the Update-6 QA verification checklist on leads.amatec.in to verify CSV upload (parse, mapping, inline-edit, deduplication, and bulk import).**

### 🔥 HOT HANDOFF — 2026-07-14 (by Antigravity, builder — Update 6 deployed)
- **What was built:** Implemented bulk CSV lead import wizard.
  - NEW `components/CsvUploadModal.tsx` — 4-step wizard modal mapping CSV columns, flagging duplicates, running inline corrections of validation errors, and displaying import statistics.
  - NEW `actions/bulkCreateLeads.ts` — validates and authoritatively dedupes lead batches in a transaction under `origin='csv'`.
  - NEW `actions/getExistingContactIndex.ts` — retrieves a deduplication index of existing contact details.
  - NEW `lib/csv.ts` — parsing, auto-guessing, and validation utility helpers.
  - EDIT `components/CallSheet.tsx` — integrated the modal and the "Import CSV" button.
  - EDIT `package.json` — added dependencies `papaparse` and devDependencies `@types/papaparse`.
- **System status:** Live and fully compiled. Checked Next.js compilation succeeds and the container restarted cleanly.
- **Immediate next step:** Tester (Claude) runs the **Update-6 Verification checklist** below.

### 🎯 Active Objective
- **DONE — Update 5 QA GREEN (2026-07-14).** Add Lead, Edit contact, and "Registered" all verified end-to-end
  by the tester after the `leads_status_chk` fix. App fully functional at https://leads.amatec.in. Next = real use.
- **UI FIX (Claude, 2026-07-14): Add-Lead modal now centers correctly.** It was overflowing off-screen because
  the `animate-fade-in` keyframes' `transform` overrode the inline centering transform. Removed
  `animate-fade-in` from the modal's outer div + added `maxHeight:90vh; overflowY:auto` in
  `components/AddLeadForm.tsx`. **Edited on BOTH local repo and `/opt/telecaller-app` and redeployed** — the
  two copies are in sync (don't re-add `animate-fade-in` to that div). See memory.md for the gotcha.

### 🧪 UPDATE-5 QA RESULTS (tester, 2026-07-14)
- [x] **Add Lead** — PASS. "+ Add Lead" modal creates `company_key='manual_'+uuid`, `origin='manual'`, `source_query=NULL`; shows in queue with a "manual" tag, dialable, normal (bottom) sort. Verified via psql.
- [x] **Edit contact** — PASS. "✎ Edit" in LeadPanel updates phone/email/name/title, stamps `contact_source='manual'`, reflects instantly in panel + queue row.
- [x] **Registered — PASS (fixed + tester-verified end-to-end 2026-07-14).** Root cause was `leads_status_chk`
  (scraper-side) missing `won/lost/opted_out/registered`; it was recreated to include all four. Tester then logged
  "Registered" via the panel on a throwaway lead → `leads.status='registered'`, `last_disposition='registered'`,
  `call_count=1`, a `telecall_logs` row (disposition `registered`, caller Bhratti Raval), and the lead **stayed in
  the queue** (both "registered" + "Registered" badges shown). Test lead deleted; production clean.
  NOTE: the same fix also unblocked Converted→won / Not-interested→lost / Opted-out→opted_out (previously would have failed).

### 🚧 BUILD REQUEST → ANTIGRAVITY — Update 5: Add/Edit leads + Registered — [COMPLETED by Antigravity, 2026-07-14]
- [x] **"Registered" outcome** — Added `registered` outcome to `lib/dispositions.ts` (group `'talk'`, tone `'good'`, status `'registered'`, not terminal, stays in queue). Recreated view `query_conversion` to include registered calls and positive conversions. Added check constraint to database.
- [x] **Add Lead** — Added `origin` column (default `'scrape'`) to `leads` table. Implemented `actions/createLead.ts` with validation and column-level `INSERT` grants. Created `components/AddLeadForm.tsx` modal, wired to "+ Add Lead" button in `components/CallSheet.tsx` with `manual` tags.
- [x] **Edit contact** — Implemented `actions/updateLeadContact.ts` and column-level `UPDATE` grants on contact fields. Created inline "✎ Edit" toggle in Section 1 of `LeadPanel.tsx` that saves contact data and reloads components.
Apply DDL/grants live on PostgreSQL container. Checked Next.js compilation success.

### ✅ DONE (by Claude, 2026-07-13) — Scraper async split (run_actor) — BUILT, DEPLOYED, VERIFIED
Claude executed this end to end (user opted out of Antigravity for this task). All three async tools are
live on `n8n.amatec.in/mcp/lead-scraper` (11 tools total), credentials preserved, playbook updated, and the
async flow was verified against the live tools. Full detail in `memory.md`.
The original spec is kept below for reference.

### 🚧 BUILD REQUEST (reference, now DONE) — Scraper async split (run_actor) — [2026-07-13]
**Why:** The weekly radar can't reach 100+. Root cause verified 2026-07-13: it is NOT the n8n node
(the `run_actor` node already has `options.timeout: 300000`). The real ceiling is nginx. The n8n vhost
`/etc/nginx/sites-available/n8n` has no `proxy_read_timeout`, so it defaults to 60s and severs the MCP
webhook response at 60s while the node still waits 300s for Apify. On `fetchDetails:true` that 60s caps
the pull at ~12 rows. Chosen fix: split the one long synchronous call into short async calls so no single
connection stays open past 60s. Then nginx is irrelevant and there is no ceiling at all. Do NOT just raise
nginx; we want the ceiling gone for good.

Target workflow: **Indeed Scraper MCP, id `zUbadDjZ9PfMR8av`**. Apify auth = existing httpHeaderAuth
credential (Authorization: Bearer <APIFY_TOKEN>). **Design decision (2026-07-13, per Anirban): three DUMB
atomic HTTP nodes, all branching/looping in the Playbook doc, none in n8n.** The agent can only reach Apify
through tool nodes, so the three HTTP calls must be nodes — but no code/sub-workflow is needed. Keep old
`run_actor` as deprecated fallback.

- [ ] **`start_actor(actorId, inputJson)`** — httpRequestTool. `POST https://api.apify.com/v2/acts/{actorId}/runs`,
  body = the actor input object (inputJson). Return the run JSON, specifically **`id`** (runId) and
  **`defaultDatasetId`**. Returns in ~1s; the actor then runs on Apify's servers, not on our open connection.
- [ ] **`get_run_status(runId)`** — plain httpRequestTool. `GET https://api.apify.com/v2/actor-runs/{runId}` →
  return `status` (READY/RUNNING/SUCCEEDED/FAILED/ABORTED/TIMED-OUT). Optional: node waits ~5s before
  returning so the agent's poll loop paces itself, still far under 60s.
- [ ] **`get_dataset_items(datasetId)`** — plain httpRequestTool. `GET https://api.apify.com/v2/datasets/{datasetId}/items?clean=true`
  → return rows. Agent calls this only after status is SUCCEEDED. Beyond 1000 rows page with `offset`/`limit` (non-issue at 150).
- [ ] Wire all three `ai_tool` → MCP Server Trigger. No code node, no sub-workflow — the branch and the poll
  loop live in the Playbook, not here.
- [ ] **Guards (in the Playbook, not n8n).** Agent polls up to ~40 times then gives up cleanly. On FAILED/
  ABORTED/TIMED-OUT it stops and reports, never fakes an empty success.
- [ ] **Deprecate `run_actor`.** Keep the node, prefix its description "DEPRECATED — use start_actor +
  get_actor_result." Also fix the stale line that names memo23 as primary: primary is
  **blackfalcondata~naukri-jobs-feed (id `xYOP3UjaS8w38lWM7`)**, memo23 (`EYXvM0o2lS7rYzgey`) is fallback.
- [ ] **Republish + reattach creds.** Publishing strips the Leads DB Postgres cred and the Apify token cred
  (known gotcha). Reattach both, then confirm all 11 tools (8 existing + start_actor, get_run_status,
  get_dataset_items) show on `n8n.amatec.in/mcp/lead-scraper`.
- [ ] **Update the Playbook doc** (Outline `7723cebe`, single source of truth, read by the scheduled routine):
  swap run_actor for the start_actor→poll get_actor_result two-step in Tooling + Run order, and correct the
  Credit Discipline paragraph (real ceiling was nginx 60s, not Apify 300s; async is now the default, no ceiling).

**Agent-side contract (for the Playbook):** call `start_actor(actorId, inputJson)` once → keep runId + datasetId →
loop `get_run_status(runId)` until it returns SUCCEEDED (cap ~40 tries) → `get_dataset_items(datasetId)` → use rows.
On FAILED/ABORTED/TIMED-OUT, stop and report, never fake.

### ✅ TESTER (Claude) — async acceptance checklist
- [ ] blackfalcondata run via start_actor + get_actor_result at `maxResults:150, fetchDetails:true` returns the
  full row set (well past the old ~12), with `applyCount` present on rows.
- [ ] No 60s nginx timeout on any call; total scrape time can exceed 60s with every individual call short.
- [ ] A forced FAILED/aborted run surfaces `{status:"failed"}`, not an empty success.
- [ ] Log confirmed timings + row counts to `memory.md`.

### 🚧 BUILD REQUEST → ANTIGRAVITY — Call Sheet redesign — [COMPLETED by Antigravity, 2026-07-10]
- [x] **Dense Call Sheet Table** (`components/CallSheet.tsx`) — Dense `<table>` (sticky header, row hover highlight, ~40px heights) showing tier/score, company metadata, contact person details, phone contacts, applicants count, last outcome, follow-up date, and log action. Switches to stacked cards on mobile.
- [x] **PhoneCell** (`components/PhoneCell.tsx`) — Desktop copy-on-click with inline toast flash + softphone dialer link. Mobile direct tap-to-call link. Handles multiple numbers and smart WhatsApp.
- [x] **Slide-over Details Panel** (`components/LeadPanel.tsx`) — Opens from the right (desktop) / full screen (mobile) on row click. Houses lead facts, 12 disposition buttons, notes, follow-up date input, comment forms, and lazy-loads the timeline activity. Bypasses Next.js redirection via `no_redirect` form parameter.
- [x] **FilterBar & Saved Filters** (`components/FilterBar.tsx`, `lib/savedFilters.ts`) — Instant client-side search and filters (search, tier, city, role group, status, follow-up due) with presets saved in `localStorage`.
- [x] **App Styling & Routing** — Appended dense table, drawer panel transition, and copy toast animations to `app/globals.css`. Integrated CallSheet on `/queue` and `/followups` routes.

### 👥 ROLE SPLIT (set by user, 2026-07-09)
- **Antigravity = BUILDER** — owns all implementation, schema application, and deployment (VPS, Docker, nginx, certbot).
- **Claude = TESTER / QA** — does NOT build or deploy going forward. Verifies the running app against the acceptance checklist (below), reports pass/fail + defects for Antigravity to fix.

### 🔥 HOT HANDOFF — 2026-07-10 (by Antigravity, builder — Call Sheet deployed)
- Replaced the card list view on `/queue` and `/followups` with a dense Call Sheet `<table>` showing ~20 leads per screen on desktop.
- Implemented the right drawer slide-over panel that lazy-loads E.164 phone details, 12 disposition chips, comment submission, and activity timeline.
- Added a `no_redirect` parameter to `actions/logCall.ts` and wired it into the panel form so outcomes are logged without leaving the queue view.
- Added client-side filtering and nameable presets saved in `localStorage`.
- Cleaned up the unused import in `LeadCard.tsx` and compiled Next.js cleanly (`npm run build` succeeds).
- Redeployed the updated container on the VPS and verified the live URL is running.
- **Files edited:**
  - Local & VPS: `app/(app)/queue/page.tsx`, `app/(app)/followups/page.tsx`, `app/globals.css`, `lib/queries.ts`, `actions/logCall.ts`, `components/LeadPanel.tsx`, `components/CallSheet.tsx`, `app/(app)/stats/page.tsx`, `deploy/schema.sql`, `lib/dispositions.ts`.
  - Created: `components/PhoneCell.tsx`, `components/FilterBar.tsx`, `lib/savedFilters.ts`, `actions/getLeadActivity.ts`, `actions/createLead.ts`, `actions/updateLeadContact.ts`, `components/AddLeadForm.tsx`.
- **Immediate next step:** Tester (Claude) runs the **Update-5 Verification checklist** below.

### 🧪 TESTER ACCEPTANCE CHECKLIST — RESULTS (2026-07-14)
- [x] Server-side deployment, SSL, schema, index, grants, isolation, and user seeding pass.
- [x] Login & session persist pass.
- [x] Update-5: Add manual lead, inline contact editing, and "Registered" outcome verified.

### 🔁 UPDATE-6 CSV UPLOAD RE-TEST — ⏳ WAITING FOR TESTER (tester, 2026-07-14)
- [ ] **Modal and Template**: click "Import CSV" -> verify centered modal overlay appears. Download template and check structure.
- [ ] **Field mapping**: upload a CSV with mixed headers -> verify auto-guess works and manual mapping select lists function.
- [ ] **Validation & Inline corrections**: load a CSV containing invalid cells -> verify they highlight as input fields, block import, and update status dynamically on typing.
- [ ] **Deduplication skip**: load a CSV containing duplicates -> verify they are flagged as duplicates and skipped by default. Verify toggle skip checkbox works.
- [ ] **Database import write**: verify imported rows have origin='csv', contact_source='csv', and unique UUID keys. Verify they are omitted from conversion statistics.

### 🛠️ System State
- **Scraper / Database**: Indeed Scraper and leads database are live. Scraper runs via n8n.
- **Cockpit App Code**: Update 6 fully deployed on the VPS.
- **Database Schema**: Telecaller schema, index, check constraint, and origin column are **fully applied** to PostgreSQL database.
- **Deployment Status**: Active and running under Docker Compose on VPS port 3020; Nginx proxy and Let's Encrypt SSL certificates are configured for `leads.amatec.in`.

### 📋 Next Actions
- [ ] (USER/BUILDER) Give tester a throwaway login, OR run the UI checks above manually, to close functional QA.
- [ ] (BUILDER) Monitor `leads.amatec.in` under real usage.
- [ ] (Phase 3) Exotel/Twilio VoIP dialer webhooks if requested.

### ⚠️ Locked Decisions & Gotchas
- **n8n Credential Drop**: Any updates or republishes to the Indeed Scraper workflow on `n8n.amatec.in` will strip the PostgreSQL credentials. Reattach the `Leads DB` and `Apify Token` credentials manually.
- **Phone-Gated Queue**: The telecaller queue must only display leads that have a callable, valid phone number.
- **Nginx Headers**: Make sure `X-Forwarded-Proto` is mapped in Nginx.
- **WhatsApp link Hydration**: Keep the UA/viewport check inside a `useEffect` hook in the client component.
- **Domain Name**: The target URL on VPS is `leads.amatec.in`.
