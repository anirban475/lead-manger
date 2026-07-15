# Lead Manager

Jobdrive's outbound lead engine and the telecaller cockpit that works those leads. This monorepo
holds both the running application and the system's design/planning workspace.

## Repository layout

| Path | What it is |
|------|------------|
| [`telecaller-app/`](telecaller-app/) | The **Telecaller Cockpit** — a Next.js 16 (App Router) web app where the telecaller sees phone-gated hot leads, taps to dial, logs call outcomes, schedules follow-ups, adds leads manually, and bulk-imports leads by CSV. Backed by an isolated Postgres `leads` database. Live at `leads.amatec.in`. |
| [`jd-lead-scrapping/`](jd-lead-scrapping/) | The **Lead Radar** design & planning workspace — system architecture, the scraper/enrichment playbooks, implementation plans, verified-facts memory, and third-party API references (Apify, PayPerWA, EPFO company-size actor). |

## The system in one paragraph

A scraper (Apify actors via a self-hosted n8n MCP) finds companies in India that are hiring now,
scores them against the Jobdrive ICP, and saves the good ones into an isolated Postgres `leads`
database. Hot leads are handed to the telecaller. The **telecaller cockpit** in `telecaller-app/`
is where those leads get called and dispositioned — and every logged outcome flows back into the
same database, closing a feedback loop the scraper reads to search better next time.

## telecaller-app — quick start

```bash
cd telecaller-app
npm install
cp .env.example .env   # fill DATABASE_URL, AUTH_SECRET, NEXT_SERVER_ACTIONS_ENCRYPTION_KEY
npm run dev            # http://localhost:3000
npm run build          # production build
```

The app connects as a least-privilege `telecaller_app` Postgres role. Schema, grants, nginx vhost,
and a user-seed script live in [`telecaller-app/deploy/`](telecaller-app/deploy/).

## Progress to date

**Live & verified**
- Scrape → score → save → Slack handoff pipeline (n8n MCP, isolated `leads` DB, learning loop).
- Async scraper split (`start_actor` / `get_run_status` / `get_dataset_items`) removing the old 60s ceiling.
- Telecaller cockpit deployed at `leads.amatec.in` (Docker + nginx + Let's Encrypt).
- Dense "Call Sheet" queue, slide-over lead panel, 13 dispositions, follow-ups, comments, unified activity timeline.
- Phone-gated queue, multi-number normalization, smart WhatsApp / tap-to-dial.
- **Update 5** — manual Add Lead, inline contact edit, "Registered" outcome (QA GREEN).
- **Update 6** — bulk **CSV lead import** wizard: upload → map columns → validate with inline-edit of
  bad cells → flag & skip duplicates (DB + in-file) → import under `origin='csv'`. Compiles clean;
  code-reviewed. Live functional QA of the import path is the current open item.

**Not yet built**
- Outreach layer (email via Mystrika, WhatsApp via PayPerWA, replies into Chatwoot).
- Optional VoIP dialer webhooks (Exotel/Twilio) to fill call duration / recording IDs.

See [`jd-lead-scrapping/CLAUDE.md`](jd-lead-scrapping/CLAUDE.md) and
[`jd-lead-scrapping/memory.md`](jd-lead-scrapping/memory.md) for the detailed handoff log and
verified system facts.
