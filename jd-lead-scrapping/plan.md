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

---

# Update 3 (2026-07-09): peer-review fixes (recommendation.md)

A second agent (Antigravity) reviewed the app. Verdicts + what's folded in. Note: the review/handoff
assume NextAuth v5, but the app uses a custom HMAC cookie session (NextAuth was dropped).

**Decision (user):** adopt #1, #2, #4, #5, #6, #7. **#3 dropped — not important** (and no code change
was needed anyway; `X-Forwarded-Proto` is already in the vhost).

1. **[CRITICAL — adopt] Multi-number phone parsing** (`lib/phone.ts`). `normalizePhone` strips all
   non-digits at once, so `"98765 43210 / 88877 66554"` or `"9876…, 9123…"` collapses into one invalid
   ~20-digit number. **Fix:** split raw input on `/`, `,`, `&`, `|`, and the word `or` FIRST; normalize
   each part; return `NormalizedPhone[]` (or add `normalizePhones()` returning an array). UI impact:
   - `components/CallButtons.tsx` renders one Call + WhatsApp pair **per valid number**.
   - `actions/logCall.ts` opt-out suppresses **every** valid number, not just the first.
   - `components/LeadCard.tsx` "callable" = ≥1 valid number. The SQL phone-gate (§D) still works
     (a multi-number string has ≥8 digits → passes), so no query change.

2. **[SECURITY — adopt] Column-level UPDATE grant** (`deploy/schema.sql`). Replace
   `GRANT SELECT, UPDATE ON leads` with:
   ```sql
   GRANT SELECT ON leads TO telecaller_app;
   GRANT UPDATE (status, next_action, next_action_date,
                 last_disposition, last_called_at, call_count) ON leads TO telecaller_app;
   ```
   App can no longer touch scraper-owned `score`/`tier`/`source_query`. (Manual-upload phase §C will
   add `INSERT` + any needed columns then.)

3. **[DROPPED — user: not important].** No change. (For reference: `X-Forwarded-Proto $scheme` is
   already in `deploy/nginx-calls.amatec.in.conf`, cookie `secure` is gated on `NODE_ENV=production`,
   and `AUTH_TRUST_HOST` is NextAuth-specific so N/A with the custom session.)

4. **[SECURITY — adopt] Login rate limiting.** Add nginx `limit_req_zone` + `limit_req` on the login
   POST in the vhost (target the `login` server action path). Files: `deploy/nginx-calls.amatec.in.conf`.

5. **[UX — adopt-lite] Smart WhatsApp link.** Mobile → `https://wa.me/<num>`; desktop →
   `https://web.whatsapp.com/send?phone=<num>`. Requires making the WhatsApp link a small client
   component (UA / viewport check). Polish item, `components/CallButtons.tsx`.

6. **[UX — adopt] Unified activity timeline.** On the lead page, merge `telecall_logs` + `lead_comments`
   into one reverse-chronological feed (call rows show disposition badge; comment rows show body),
   instead of two separate cards. Files: `app/(app)/leads/[company_key]/page.tsx`, `lib/queries.ts`
   (fetch both and merge by `called_at`/`created_at`, or a UNION query).

7. **[PERF — adopt-partial] Indexes.** `leads(source_query)` is ALREADY indexed
   (`idx_leads_source_query`). Add `CREATE INDEX IF NOT EXISTS idx_telecall_logs_disposition
   ON telecall_logs(disposition);` for the conversion view. Files: `deploy/schema.sql`.

**Net delta files:** `lib/phone.ts`, `components/CallButtons.tsx`, `actions/logCall.ts`,
`components/LeadCard.tsx`, `app/(app)/leads/[company_key]/page.tsx`, `lib/queries.ts`,
`deploy/schema.sql`, `deploy/nginx-calls.amatec.in.conf`. Then `npm run build`.

---

# Update 4 (2026-07-10): "Call Sheet" UX redesign — density + speed

## Context
The app is live and functionally green, but Bhratti finds the UX too slow for high-volume calling:
the card-list → open a full **detail page** → scroll → act flow needs too many clicks and too much
scrolling, and adding a comment takes several clicks. Her benchmark is the **Google Sheet** she uses
today: dense, everything visible, fast. Redesign the queue into a **call sheet** — maximum info per
screen on desktop, minimal clicks, quick dial, and log/comment **without leaving the list**.

**Decisions (from user):**
- **Dense table on desktop**, max info on one screen (~15–20 leads), fewer clicks.
- **Filters + SAVED filter presets** (save a filter and reuse it).
- **Slide-over panel** (right drawer) to view details + log outcome + add a note/comment **during the call**.
- **Two-device workflow**: she operates the app on desktop and dials from her phone. On **desktop** the
  number is **click-to-copy ("Copied ✓") + a small Call (`tel:`) link** (for a softphone); on **mobile**
  it is `tel:` tap-to-dial. Responsive; both devices used together.

## Design

### 1. Queue → dense Call Sheet (`components/CallSheet.tsx`, new client component)
Replaces the `LeadCard` list in `app/(app)/queue/page.tsx` (server still fetches via `getQueue`, passes
the ≤200 leads down). Desktop = a **dense `<table>`** with sticky header, ~40px rows, hover highlight.
Columns: tier/score chip · Company (city · role_group · industry_label as subtext) · Contact (name ·
title) · **Phone (PhoneCell)** · Apply-count · Status/last outcome · Follow-up · **[Log]**. Row click or
[Log] opens the slide-over for that lead. Mobile = compact stacked rows (company + contact + big
Call/Copy) that open the panel full-screen.

### 2. Filter bar + saved filters (`components/FilterBar.tsx`, `lib/savedFilters.ts`)
Client-side filtering over the already-loaded leads (instant, no round-trips): free-text search
(company/contact), tier chips, dropdowns for status / role_group / city / "follow-up due", clear-all.
**Saved filters**: "Save current filter" → named preset; apply/delete. Store in **localStorage**
(per-device, zero backend) for v1. *(Cross-device sync later = a small `saved_filters(user_email, name,
params jsonb)` table + grant — deferred.)*

### 3. Slide-over panel (`components/LeadPanel.tsx`, new client component)
Opens from the right (desktop) / full-screen sheet (mobile). Contains: company header, "Ask for
{name} · {title}", PhoneCell (copy/dial), key facts (city, size, apply_count, email, website, roles,
source_query), the **12 disposition chips** (big tap targets), a **note** field, conditional follow-up
date, **Save** (logs the call), a **quick-comment** field, and the **unified activity timeline**.
Everything for a call in one place → ~2 taps to log, no navigation, no long scroll.
- Reuse existing server actions **`logCall`** and **`addComment`** (already working) as the panel's writes.
- Load activity lazily on open: add **`getLeadActivity(companyKey)`** to `lib/queries.ts` reusing
  `getLeadCalls` + `getLeadComments` (or call them from a small server action). Revalidate `/queue` on save.
- Keep `/leads/[company_key]` as a deep-link fallback; the panel is the primary path.

### 4. Phone dial/copy (`components/PhoneCell.tsx`, new client component)
Same UA/viewport check pattern as `CallButtons.tsx`. **Desktop: show the number as click-to-copy
(`navigator.clipboard.writeText` + "Copied ✓" flash) AND a small Call icon/link that fires `tel:`**
(for a softphone). **Mobile: tap the number → `tel:` dialpad.** Uses `normalizePhones` so multi-number
leads expose/copy/call each number. Smart WhatsApp link stays available.

### 5. Responsive
Desktop: dense table + right slide-over. Mobile: compact call-list rows + full-screen panel + `tel:` dial.
CSS additions (dense table, sticky thead, slide-over, toast) go in `app/globals.css`, reusing existing tokens.

## Files
- Edit: `app/(app)/queue/page.tsx` (render `CallSheet`), `app/globals.css` (table/drawer/toast styles),
  `lib/queries.ts` (add `getLeadActivity`), optionally `app/(app)/followups/page.tsx` (reuse CallSheet).
- New: `components/CallSheet.tsx`, `components/FilterBar.tsx`, `components/LeadPanel.tsx`,
  `components/PhoneCell.tsx`, `lib/savedFilters.ts`.
- Reuse (no change): `actions/logCall.ts`, `actions/addComment.ts`, `lib/phone.ts`
  (`normalizePhones`), `lib/dispositions.ts`, `getLeadCalls`/`getLeadComments`. `components/LeadCard.tsx`
  is retired from the queue (kept only if the fallback detail route wants it).

## Verification
- **Desktop density:** 15–20 leads visible without scroll; search filters instantly; save a filter →
  reload → apply it.
- **Dial/copy:** click a phone on desktop → "Copied ✓", clipboard holds the E.164; on a phone, tapping
  opens the dialpad (`tel:`).
- **Panel:** click a row → panel opens with details + dispositions + note + timeline; pick a disposition
  + note → Save → row updates and a `telecall_logs` row appears (verify via psql); add a comment → shows
  in the timeline. All without leaving the list.
- **Regression:** phone-gate still hides phone-less leads; opt-out still suppresses; `npm run build` green.
- Clean up any test writes via admin psql after verifying (tester practice).

## Open item
- Saved-filter storage: **localStorage (per-device)** recommended for v1; DB-backed cross-device sync deferred.

---

# Update 5 (2026-07-11): Add/Edit leads + "Registered" status

## Context
Telecallers need to (1) **add their own leads**, (2) **fix a lead's phone/email/contact person**, and
(3) mark a company **"Registered"** (signed up). User decisions: Registered is a **logged call outcome
that KEEPS the lead in the queue** (not terminal); manually-added leads sort in their **normal scored
position** (no special placement). All additive; isolation + scraper-learning hygiene preserved.

## 1. "Registered" disposition + status
- `lib/dispositions.ts`: add `registered` — group `'talk'`, tone `'good'`, label "Registered".
  `STATUS_MAP.registered = 'registered'`; NOT in `NEEDS_FOLLOWUP`; **NOT in `CLOSED`** (stays in queue).
- `lib/queries.ts`: `CLOSED` stays `('won','lost','opted_out')`. `leads.status` is free-text → no DDL for
  the status itself. Registered leads keep showing (StatusBadge "registered") and are filterable via the
  existing status dropdown. The chip auto-appears in `LeadPanel`/`LogCallForm` (they render from
  `DISPOSITION_META`) — no UI change.
- DDL (`deploy/schema.sql`) — extend the telecall_logs CHECK to 13 values:
  ```sql
  ALTER TABLE telecall_logs DROP CONSTRAINT telecall_logs_disposition_chk;
  ALTER TABLE telecall_logs ADD CONSTRAINT telecall_logs_disposition_chk CHECK (disposition IN (
    'no_answer','busy','call_dropped','invalid_number','connected','info_shared','interested',
    'callback','meeting_booked','not_interested','converted','opted_out','registered'));
  ```
- `query_conversion` view: add `registered` to the `positive_companies` filter (+ a `registered_calls`
  column) — the strongest conversion signal for the scraper.

## 2. Add Lead (manual entry)
- DDL: `ALTER TABLE leads ADD COLUMN IF NOT EXISTS origin text DEFAULT 'scrape';`
- New `actions/createLead.ts` (`'use server'`, auth-checked): validate company_name + ≥1 valid phone
  (`normalizePhones`); INSERT `company_key='manual_'+crypto.randomUUID()`, `origin='manual'`,
  `status='new'`, `contact_source='manual'`, `source_query=NULL` (→ excluded from `query_conversion`,
  never pollutes scraper learning). `revalidatePath('/queue')`.
- Grant (column-level INSERT):
  ```sql
  GRANT INSERT (company_key, company_name, contact_phone, contact_email, contact_name,
                contact_title, contact_source, city, status, origin, created_at, updated_at)
    ON leads TO telecaller_app;
  ```
- UI: "+ Add Lead" button in the queue header/FilterBar → new `components/AddLeadForm.tsx` (modal):
  Company*, Phone*, Email, Contact person, Title, City → submit → refresh. Sorts in normal scored
  position (no score → near bottom, per user). Small "Manual" tag on the row/panel for identification.
- `lib/queries.ts`: add `origin` to `Lead` + `LEAD_COLS`.

## 3. Edit lead contact (phone / email / contact person)
- New `actions/updateLeadContact.ts` (`'use server'`, auth-checked): `UPDATE leads SET contact_phone,
  contact_email, contact_name, contact_title, contact_source='manual', updated_at=now()
  WHERE company_key=$1`. Revalidate `/queue` + the lead.
- Grant (adds to existing column-level UPDATE):
  ```sql
  GRANT UPDATE (contact_phone, contact_email, contact_name, contact_title, contact_source)
    ON leads TO telecaller_app;
  ```
- **Safe under re-scrape**: `save_leads` COALESCE-preserves contact for in-play leads, so hand-fixes survive.
- UI: in `components/LeadPanel.tsx` Section 1 (Quick Contacts), add an "✎ Edit" toggle revealing inputs
  for phone / email / contact name / title → Save → `updateLeadContact` → reload panel + queue
  (`onLeadUpdated`). No navigation.

## Files
- Edit: `lib/dispositions.ts`, `lib/queries.ts` (Lead+origin), `deploy/schema.sql` (CHECK, origin col,
  grants, view), `components/LeadPanel.tsx` (edit-contact), `components/CallSheet.tsx` + `FilterBar.tsx`
  (+Add Lead button; optional Manual tag), optionally `app/(app)/stats/page.tsx` (registered count).
- New: `actions/createLead.ts`, `actions/updateLeadContact.ts`, `components/AddLeadForm.tsx`.
- Reuse: `normalizePhones` (lib/phone.ts), existing drawer/toast patterns, `getSession` auth guard.

## Verification
- **Registered**: log "Registered" on a test lead → telecall_logs row (disposition registered) +
  status 'registered'; lead STILL in queue with a 'registered' badge; `query_conversion` counts it.
- **Add lead**: add "Test Co / +9198…" → appears in queue, dialable, opens in panel; DB row has
  `company_key 'manual_…'`, `origin 'manual'`, `source_query NULL`; absent from `query_conversion`.
- **Edit contact**: change a lead's phone/contact in the panel → persists (psql); re-run `save_leads`
  for that key → the edit survives (COALESCE).
- **Isolation**: as `telecaller_app`, INSERT touches only granted columns; DELETE still fails; no
  `radar_runs`. `npm run build` green. Clean up test rows via admin psql.
