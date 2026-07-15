# Telecalling Cockpit for Bhratti — Implementation Plan

## Context

The Jobdrive lead radar already scrapes, scores, and stores companies in an isolated Postgres
`leads` database, then hands hot leads to Bhratti over Slack. There is **no interface for the
telecaller** — she works leads out of Slack DMs, and her call outcomes are lost. Nothing flows
back to the scraper, so it can only learn from "how many hot leads did a query produce," never
from "how many actually converted on the phone."

This plan builds a small responsive **web cockpit** where Bhratti (and 3–6 teammates) can see hot
leads, tap-to-dial, log the call outcome, and schedule follow-ups. Every logged disposition is
written to the same Postgres the scraper reads, closing a **feedback loop**: the scraper learns
which `source_query` values yield *conversations*, not just hot counts, and searches/filters better.

**Decisions locked with the user:**
- Stack: **custom Next.js (App Router)**, reusing the existing Jobdrive design tokens.
- Device: **responsive — mobile + desktop** (reviews on desktop, calls from mobile).
- Dispositions: **all** (connected, no_answer, wrong_number, not_interested, interested, callback, converted, meeting_booked, opted_out).
- Calling: **tap-to-dial now** (`tel:` / `wa.me`); schema built so a real dialer (Exotel/Twilio) slots in later.
- v1 = **lean cockpit** (queue → dial → log-call → follow-ups). Stats + scraper feedback come in phase 2.
- Users: **small team (3–6)** with **per-caller attribution** on every logged call.

## Key facts that shape the build (verified)

- The `leads` Postgres is **isolated on Docker network `shared-network`** (host `shared-postgres:5432`,
  db `leads`, role `leads_user`, PUBLIC revoked). Not reachable from outside the VPS → the app must
  run **as a container on the VPS joined to `shared-network`** (an external host like Vercel can't
  reach it without breaking isolation). This is good: one source of truth, no sync.
- The scraper's `save_leads` upsert, on conflict, only updates `roles_count, role_titles, posted_date,
  job_urls, score, tier, updated_at` and COALESCE-preserves everything else. **New columns we add to
  `leads` are never touched by a re-scrape** — no MCP change needed to protect feedback data.
- Reverse proxy on the VPS is **host-level nginx + certbot** (per-subdomain vhosts in
  `/etc/nginx/sites-available/`, TLS via Let's Encrypt). Reference vhost: `/etc/nginx/sites-available/sales.amatec.in`.
- Confirmed way onto `shared-network`: the `networks: default: external: true, name: shared-network`
  pattern from `/opt/n8n-hosting/client1/docker-compose.yml`.
- Reuse design tokens from `/Users/anirban/Library/CloudStorage/OneDrive-Personal/Desktop/Claude/Design/jobdrive-ui/design-system/`
  (`styles.css` → tokens: Quicksand font, `--color-primary: #38bdf8`, `--surface-sidebar: #111827`,
  ready-made badge tints, and a dark theme via `data-theme`).

## Architecture

- **Next.js App Router + TypeScript**, single container. Server Components for reads
  (queue / detail / follow-ups / stats); **Server Actions** for the two writes (log-call, opt-out).
  No separate API tier.
- **DB access:** `pg` (node-postgres) singleton `Pool` connecting as a **new least-privilege role
  `telecaller_app`** to `shared-postgres:5432/leads`, SSL off. Never reuse `leads_user`.
- **Auth:** Auth.js (NextAuth v5) **Credentials provider** backed by an `app_users` table in the
  `leads` db (email + bcrypt hash + display_name + role), JWT cookie, middleware guards all routes.
  Users seeded via SQL. `display_name` becomes the `caller` on every logged call (per-caller attribution).
- **Isolation preserved:** app only touches `leads` (SELECT/UPDATE), `telecall_logs` (INSERT),
  `suppression` (INSERT), `query_conversion` (SELECT), `app_users` (SELECT). No DELETE anywhere,
  never touches `radar_runs`, never runs the scraper upsert.

## Schema changes (all additive)

Apply this DDL to the `leads` db (as owner/`leads_user`), then create the app role.

```sql
-- 1. Append-only call log (per-caller attribution via `caller`)
CREATE TABLE telecall_logs (
    id               bigserial PRIMARY KEY,
    company_key      text NOT NULL REFERENCES leads(company_key) ON DELETE CASCADE,
    called_at        timestamptz NOT NULL DEFAULT now(),
    caller           text NOT NULL,                 -- app_users.display_name
    channel          text NOT NULL DEFAULT 'tel',   -- 'tel' | 'whatsapp' | 'exotel' | 'twilio'
    disposition      text NOT NULL,
    reason           text,
    notes            text,
    follow_up_date   date,
    duration_seconds int,                            -- nullable; real dialer fills later
    external_call_id text,                           -- nullable; Exotel/Twilio SID later
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT telecall_logs_disposition_chk CHECK (disposition IN
      ('connected','no_answer','wrong_number','not_interested','interested',
       'callback','converted','meeting_booked','opted_out'))
);
CREATE INDEX idx_telecall_logs_company_key ON telecall_logs(company_key);
CREATE INDEX idx_telecall_logs_called_at   ON telecall_logs(called_at);

-- 2. Denormalized latest-call fields on leads (safe: outside save_leads' update list)
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_disposition text;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_called_at   timestamptz;
ALTER TABLE leads ADD COLUMN IF NOT EXISTS call_count       int NOT NULL DEFAULT 0;

-- 3. Per-query conversion signal (the feedback view the scraper reads)
CREATE OR REPLACE VIEW query_conversion AS
SELECT
    l.source_query,
    count(DISTINCT l.company_key)                               AS companies,
    count(DISTINCT l.company_key) FILTER (WHERE l.tier='hot')   AS hot_companies,
    round(avg(l.score),1)                                       AS avg_score,
    count(DISTINCT t.company_key)                               AS contacted_companies,
    count(t.id) FILTER (WHERE t.disposition='interested')       AS interested_calls,
    count(t.id) FILTER (WHERE t.disposition='converted')        AS converted_calls,
    count(t.id) FILTER (WHERE t.disposition='meeting_booked')   AS meeting_calls,
    count(DISTINCT t.company_key) FILTER
      (WHERE t.disposition IN ('interested','converted','meeting_booked')) AS positive_companies
FROM leads l
LEFT JOIN telecall_logs t ON t.company_key = l.company_key
WHERE l.source_query IS NOT NULL
GROUP BY l.source_query;

-- 4. Auth users
CREATE TABLE app_users (
    id serial PRIMARY KEY, email text UNIQUE NOT NULL,
    password_hash text NOT NULL, display_name text, role text DEFAULT 'caller',
    created_at timestamptz DEFAULT now());

-- 5. Least-privilege app role
CREATE ROLE telecaller_app LOGIN PASSWORD '<<generate-strong>>';
GRANT CONNECT ON DATABASE leads TO telecaller_app;
GRANT USAGE  ON SCHEMA public   TO telecaller_app;
GRANT SELECT, UPDATE ON leads         TO telecaller_app;
GRANT SELECT, INSERT ON telecall_logs TO telecaller_app;
GRANT USAGE, SELECT ON SEQUENCE telecall_logs_id_seq TO telecaller_app;
GRANT SELECT, INSERT ON suppression   TO telecaller_app;
GRANT SELECT ON query_conversion      TO telecaller_app;
GRANT SELECT ON app_users             TO telecaller_app;
-- No DELETE anywhere; no access to radar_runs.
```

**Log-call = one transaction** (Server Action `actions/logCall.ts`): INSERT into `telecall_logs`,
then UPDATE `leads` (status, next_action, next_action_date=follow_up_date, last_disposition,
last_called_at=now(), call_count+1). If `disposition='opted_out'`: also force `status='opted_out'`
and `INSERT INTO suppression(contact, reason) VALUES (<e164>, 'telecall_opt_out') ON CONFLICT DO NOTHING`.

**Disposition → `leads.status` mapping** (keeps the scraper's existing status vocabulary):
`converted→won`, `not_interested→lost`, `opted_out→opted_out`, `interested/callback/meeting_booked→hot`,
`connected/no_answer/wrong_number→handed_off`. (Confirm this mapping with Anirban during build.)

## App structure

```
telecaller-app/
  Dockerfile                       # node:22-alpine, next build && next start, EXPOSE 3000
  docker-compose.yml               # joins shared-network (client1 pattern)
  .env                             # DATABASE_URL, AUTH_SECRET, AUTH_URL
  app/
    layout.tsx                     # imports jobdrive tokens; Quicksand; app shell
    globals.css                    # @import design-system styles.css + tokens
    (auth)/login/page.tsx          # Credentials sign-in
    (app)/layout.tsx               # dark sidebar (#111827) desktop / bottom tab bar mobile
    (app)/queue/page.tsx           # HOT QUEUE (default) — score desc, filter tier/status
    (app)/leads/[company_key]/page.tsx  # detail + <LogCallForm/> (Server Action)
    (app)/followups/page.tsx       # next_action_date <= today
    (app)/stats/page.tsx           # phase 2: dispositions + query_conversion
  lib/  db.ts (pg Pool) · queries.ts · phone.ts · dispositions.ts
  actions/  logCall.ts ('use server', transactional)
  auth.ts · middleware.ts
  components/  LeadCard · ScoreBadge · TierBadge · DispositionPill · CallButtons · LogCallForm · StatBar
```

- **Queue query:** `ORDER BY score DESC, (next_action_date <= current_date) DESC, posted_date DESC NULLS LAST`;
  filters `tier`/`status` via querystring; show a "needs enrichment" chip when `contact_phone IS NULL OR contact_phone='-'`.
- **Responsive:** sidebar → bottom tab bar under 768px; queue = table on desktop, card list on mobile;
  large `CallButtons` tap targets. Dark mode free via `data-theme`.
- **Phone normalization (`lib/phone.ts`):** null/empty/`'-'` → `needs_enrichment` (render a muted chip,
  never a dead link); strip to digits/`+`; 10-digit starting 6–9 → `+91…`; `0`-prefixed 11-digit → `+91…`;
  `91`-prefixed 12-digit → `+…`; else best-effort `+…` flagged low-confidence. `tel:<e164>` and
  `https://wa.me/<e164 without +>`. Store the E.164 form as `suppression.contact` so opt-outs match future scrapes.

## Feedback loop into the scraper

The `query_conversion` VIEW lives in the same `leads` db the lead-radar scraper already connects to.
**Phase 2 (zero MCP cost):** extend the lead-radar skill's existing `get_query_yield` Postgres read to
also `SELECT * FROM query_conversion` through the credential it already uses — no new node, no republish.
**Phase 3 (optional):** expose a discrete `get_query_conversion` MCP tool — but **batch it with any other
n8n change** because every `update_workflow + publish_workflow` on workflow `zUbadDjZ9PfMR8av` strips the
`Leads DB` credential and it must be manually reattached (documented gotcha). The VIEW is the real signal;
a new tool is not required on day one.

## Phased delivery

- **Phase 0 — DB:** apply the DDL, create `telecaller_app`, seed 2 bcrypt users. Verify grants.
- **Phase 1 — MVP cockpit (v1):** auth, DB client, Queue, Lead detail + Log-call (transactional, opt-out→suppression),
  Follow-ups/Today view, tap-to-dial + WhatsApp. Deploy to `calls.amatec.in`.
- **Phase 2 — stats + feedback:** Stats page (dispositions + `query_conversion`); wire the VIEW into the
  lead-radar skill's existing read.
- **Phase 3 — optional:** `get_query_conversion` MCP tool (batched republish); real-dialer webhook fills
  `duration_seconds` / `external_call_id` / `channel`.

## Deployment (this VPS, concrete)

Develop locally in `telecaller-app/` under the working directory; deploy to `/opt/telecaller-app/` on the VPS.

1. `docker-compose.yml` joins `shared-network` (client1 pattern), publishes a free host port (**3020** —
   verify with `ss -ltnp`; 80/443/3000/5001/5010/5432/5433/5440/5678/5679/4174/4180/6379 are taken).
   `env_file` sets `DATABASE_URL=postgres://telecaller_app:***@shared-postgres:5432/leads`.
2. `docker compose up -d --build`; confirm `docker network inspect shared-network` lists `telecaller-app`
   and `nc -z shared-postgres 5432` from inside it.
3. DNS A record `calls.amatec.in → VPS IP`, then `certbot --nginx -d calls.amatec.in`.
4. nginx vhost `/etc/nginx/sites-available/calls.amatec.in` mirroring `sales.amatec.in` (single upstream
   `proxy_pass http://127.0.0.1:3020;` + Let's Encrypt TLS block); symlink into `sites-enabled/`,
   `nginx -t`, `systemctl reload nginx`.

## Verification (end to end)

- **Grants/isolation:** as `telecaller_app`, `INSERT INTO radar_runs` and `DELETE FROM leads` fail;
  SELECT/UPDATE `leads`, INSERT `telecall_logs`, SELECT `query_conversion` succeed.
- **Upsert safety:** set `last_disposition` on a test lead, re-run `save_leads` for its `company_key`,
  confirm the denorm fields survive and only score/tier/roles refresh.
- **Log-call:** log each of the 9 dispositions; confirm a `telecall_logs` row + correct
  `leads.status`/`next_action_date`/denorm fields, and `caller` = the signed-in user's display name.
- **Opt-out:** `opted_out` writes a `suppression` row (E.164 contact) + sets `status='opted_out'`; re-run → no dupe.
- **Follow-ups:** `follow_up_date = today` → lead appears in Today view.
- **Phone edge cases:** `'-'`, null, `98765 43210`, `+91 98765 43210`, `098765…` normalize/flag correctly.
- **Feedback:** `query_conversion` returns per-`source_query` interested/converted/meeting counts matching seeded logs.
- **Deploy/TLS:** `https://calls.amatec.in` loads with a valid cert; mobile tab bar + desktop table both render;
  `tel:`/`wa.me` fire on a phone.

## Risks / gotchas

- **MCP credential-drop:** any republish of `zUbadDjZ9PfMR8av` strips the `Leads DB` credential — reattach
  manually. Prefer the VIEW-through-existing-read path; batch any real MCP change.
- **Isolation:** app connects only as `telecaller_app` (no DELETE, no `radar_runs`); PUBLIC stays revoked.
- **Opt-out consistency:** the opted_out path must be one transaction (log + status + suppression) using the
  normalized E.164 contact, so future scrapes suppress correctly.
- **Denorm columns are safe only because they're outside `save_leads`' update list** — do not add them to
  that list later without revisiting.
- **Network naming:** the app must join `shared-network` exactly (not the similarly named `shared-net`, and
  not the n8n main `amatec-net`) — that's the one holding `shared-postgres`.

## Key files

- `telecaller-app/docker-compose.yml` (new — shared-network join)
- `telecaller-app/lib/db.ts`, `telecaller-app/actions/logCall.ts` (new — pool + transactional write)
- `/etc/nginx/sites-available/calls.amatec.in` (new — mirrors `/etc/nginx/sites-available/sales.amatec.in`)
- `/opt/n8n-hosting/client1/docker-compose.yml` (reference — shared-network + shared-postgres pattern)
- `.../jobdrive-ui/design-system/styles.css` + `tokens/colors.css`, `tokens/fonts.css` (design tokens to import)

---

# Update 2 (2026-07-09): new DB fields + real telecalling model

After the app was built, two things changed. Both are now folded in as deltas.

## Build status (as of pause — planning only, nothing deployed)
- **App code: fully built and green** (`next build` passed) — `telecaller-app/` (Next.js 16 App
  Router): auth, queue, lead detail, log-call, follow-ups, stats, Dockerfile/compose, deploy runbook.
- **Delta edits started** (local files only, not built/deployed): `lib/dispositions.ts` (12 grouped
  dispositions), `lib/queries.ts` (5 new columns + phone-gate + `getLeadComments`), `deploy/schema.sql`
  (12-value CHECK + `lead_comments` table + grants).
- **Delta edits still pending**: `components/LeadCard.tsx` (contact_name/apply_count; drop enrichment
  chip), `app/(app)/leads/[company_key]/page.tsx` (Ask-for line, apply_count, Comments card),
  `components/LogCallForm.tsx` (grouped radios), new `actions/addComment.ts` + `components/CommentForm.tsx`,
  then `npm run build`.
- **NOT started / never touched the live system**: DB schema NEVER applied to Postgres (only a draft
  SQL file); no `telecaller_app` role; no users seeded; container not built/deployed; no nginx/DNS.
- **Future phase (not v1)**: Bhratti lead-upload feature (§C) — deferred.

## A. Five new `leads` columns (scraper evolved) — surface them
The live `leads` table gained: `apply_count int`, `role_group text`, `industry_label text`,
`contact_name text`, `contact_title text`. These are exactly what a caller needs (they mirror the
old Google Sheet's "Call person name"), so:
- Add all five to `Lead` (lib/queries.ts) and to `LEAD_COLS`.
- **LeadCard**: show `contact_name` ("Ask for …"), an `apply_count` badge (the pressure hook, e.g.
  "873 applicants"), and `role_group` / `industry_label` tags; prefer `industry_label` over `industry`.
- **Lead detail**: lead with **"Ask for {contact_name} · {contact_title}"** beside the call buttons,
  and show `apply_count` prominently as the "why call now" signal.
- **Queue sort**: add `apply_count DESC NULLS LAST` as a tiebreaker after `score`.
- `size` is now more reliably populated (scraper resolves CIN via `get_company_size`); keep showing it.

## B. Expanded, telecaller-real disposition model (chosen)
The old Google Sheet shows how calls are really logged (busy / dropped / unreachable / "shared on
WhatsApp" are distinct, frequent outcomes). Replace the lean 9 with **12 grouped dispositions** in
`lib/dispositions.ts` (and add a `group` field for the UI):

- **Couldn't connect** (`group:'reach'`): `no_answer`, `busy`, `call_dropped`, `invalid_number`
  (invalid_number replaces `wrong_number`; covers not-in-use / out-of-service / not-reachable).
- **Talked** (`group:'talk'`): `connected`, `info_shared` (sent details on WA/mail — their most common
  positive step), `interested`, `callback`, `meeting_booked`, `not_interested`, `converted`, `opted_out`.

Tones: reach outcomes `warn` except `invalid_number` = `bad`; `connected` neutral; `info_shared`,
`interested`, `meeting_booked`, `converted` = `good`; `callback` warn; `not_interested`, `opted_out` = `bad`.

`STATUS_MAP`: `not_interested→lost`, `converted→won`, `opted_out→opted_out`,
`info_shared/interested/callback/meeting_booked→hot`, `no_answer/busy/call_dropped/invalid_number/connected→handed_off`.
`NEEDS_FOLLOWUP` (offer a follow-up date): `no_answer, busy, call_dropped, callback, interested, info_shared, meeting_booked`.

**DDL impact** (schema not yet applied — no migration): update the `telecall_logs`
`disposition CHECK` in `deploy/schema.sql` to the 12 values. **LogCallForm**: render the two labeled
groups instead of one flat grid.

## C. Do NOT import the historical sheet — but plan a lead-upload feature (future)
The 176-row sheet is a *different segment* (recruiters being sold Jobdrive) and those companies aren't
in the leads DB — leave it as a legacy archive; do not migrate it in. Separately, Bhratti wants to
**add her own leads into the system in future**. Scope that as a later phase, not v1:
- "Add lead" form + CSV upload. Manual leads get `company_key = 'manual_<random>'`, `source_query = NULL`,
  and a new `origin text DEFAULT 'scrape'` column set to `'manual'`.
- Keeps them **out of the scraper's learning signal**: `query_conversion` already filters
  `source_query IS NOT NULL`, so manual leads never distort per-query conversion.
- Requires `GRANT INSERT ON leads TO telecaller_app` (add when building this phase).

## Delta files to touch
`lib/queries.ts` (Lead + LEAD_COLS + queue sort), `lib/dispositions.ts` (12 grouped dispositions,
maps), `components/LeadCard.tsx` and `app/(app)/leads/[company_key]/page.tsx` (contact_name/title +
apply_count), `components/LogCallForm.tsx` (grouped radios), `deploy/schema.sql` + Phase 0 DDL
(CHECK list). Manual-upload feature deferred to a later phase.

## D. Phone-gated visibility (caller only sees callable leads)
Bhratti is a telecaller — a lead with no phone is useless to her (it belongs to the enrichment step).
So **Queue and Follow-ups only show leads with a usable phone number**:
- Add to the `WHERE` of `getQueue` and `getFollowups` (lib/queries.ts):
  `contact_phone IS NOT NULL AND length(regexp_replace(contact_phone, '[^0-9]', '', 'g')) >= 8`
  (mirrors `normalizePhone`'s validity threshold; also excludes `'-'` and blanks).
- Drop the "needs enrichment" chip from LeadCard (phone-less leads no longer appear). Keep it on the
  lead-detail page only as a safety net if reached by direct link.

## E. Comments (freeform per-lead notes, any time)
Separate from logging a full call outcome, she can drop a comment on a lead:
- New table `lead_comments (id bigserial PK, company_key text REFERENCES leads ON DELETE CASCADE,
  author text NOT NULL, body text NOT NULL, created_at timestamptz DEFAULT now())` + index on company_key.
  Grants: `SELECT, INSERT` + sequence to `telecaller_app`.
- New server action `actions/addComment.ts` (`'use server'`, auth-checked, insert + revalidate the lead page).
- Lead detail: a "Comments" card with a textarea + submit, and the thread (author · time · body),
  newest first. Reuses the existing `.card`/`.call-log-item` styles.
- Add `getLeadComments(companyKey)` to lib/queries.ts.

## F. Mobile one-tap dialing (first-class requirement)
Bhratti mostly works from her phone, so tap-to-call must be frictionless:
- Every number is a `tel:<E.164>` link → **one tap opens her phone's dialer pre-filled**; she presses
  call. The number is normalized to `+91…` E.164 first (lib/phone.ts) so the dialer gets a clean number.
- On the lead screen the **primary CTA is a large, full-width "📞 Call {number}" button** (min ~48px
  tap height via `.btn.lg` / `.call-row`), WhatsApp (`wa.me`) beside it.
- **Mobile-first responsive** (already in globals.css `@media max-width:768px`): sidebar → bottom tab
  bar, single-column cards, enlarged buttons. Verify on a real phone, not just desktop-narrow.
- The phone-gate (§D) guarantees every lead she opens has a dialable number — no dead ends.
- Acceptance: on an actual phone, tapping the number/Call button on a lead opens the dialer with the
  number loaded, ready to call in one press.

## Verification additions
- Queue/detail show `contact_name`, `contact_title`, `apply_count` for `cs_`-keyed pharma leads
  (e.g. Sunrise Remedies 873, Expert Pharmaceuticals 1,985).
- Log each of the 12 dispositions; CHECK constraint accepts all 12; `busy`/`call_dropped`/`invalid_number`
  land as distinct rows; `info_shared` sets status `hot` and offers a follow-up date.
- Queue hides phone-less leads: a lead with `contact_phone` blank/`'-'`/`''` (e.g. Expert
  Pharmaceuticals has email but no phone) does NOT appear in the queue; leads with a valid phone do.
- Add a comment on a lead → it appears in the comment thread with the signed-in caller as author,
  and persists independently of any call log.
