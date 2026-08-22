# Lead Manager

Jobdrive's outbound lead engine and the telecaller cockpit that works those leads. This monorepo
holds both the running application and the system's design/planning workspace.

## Repository layout

| Path | What it is |
|------|------------|
| [`telecaller-app/`](telecaller-app/) | The **Telecaller Cockpit** — a Next.js 16 (App Router) web app where the telecaller sees phone-gated hot leads, taps to dial, logs call outcomes, schedules follow-ups, adds leads manually, and bulk-imports leads by CSV. Backed by an isolated Postgres `leads` database. Live at `leads.amatec.in`. |
| [`jd-lead-scrapping/`](jd-lead-scrapping/) | The **Lead Radar** design & planning workspace — system architecture, the scraper/enrichment playbooks, implementation plans, verified-facts memory, and third-party API references (Apify, PayPerWA, EPFO company-size actor). |
| [`jd-lead-newspaper/`](jd-lead-newspaper/) | The **Newspaper Radar** — classified-ad lead extraction, indupaper fetch contracts, and the standing Tesseract OCR service. |
| [`sql/migrations/`](sql/migrations/) | Migrations against the `leads` database. Numbered, additive. |
| [`tools/`](tools/) | Operational scripts. Anything that writes to the database defaults to a dry run and requires an explicit `--apply`. |
| `actions/` | Live work briefs for the Antigravity agent. **Should be empty between jobs.** A spent brief left here invites a later run to re-execute finished work against assumptions that have moved. |

## Repo traps

Things that have already cost time. Read before committing.

**`.gitignore` line 31 is `*.py`.** Every Python file needs `git add -f` or the commit silently
omits it. There are per-file negations below that line for a handful of scripts, so a file
committing successfully is not proof the next one will.

**Anything writing to the `leads` database must default to a dry run.** `--apply` is opt in.
When shelling out to `psql`, pass `-v ON_ERROR_STOP=1`, otherwise psql continues past a failed
statement, still reaches `COMMIT`, and exits `0`. A partial write then reports success.

**Never change `status` on an existing lead** as a side effect of a re-extract or a backfill.

**`ad_key` is a hash of the ad text.** Any change to newspaper segmentation moves the boundaries,
so ad_keys change and layer 1 treats every segment as new. Deduplication on contact is what stops
that duplicating the lead book. Prove it with a dry run before writing.

**`trigger_type` on Amatec leads is deliberately the single value `ops_role_posted`.** The posted
job function lives in `role_group`. Putting the function in `trigger_type` forces every routing
rule to enumerate the functions and breaks silently the day a new one appears.

**`country` may be null and that is never a reason to exclude a lead.** It sets a send window,
nothing more. Bare `CA` in `source_query` is ambiguous between Canada and California and is left
unresolved on purpose; `Canada` spelled out maps to `CA`.

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
- **Newspaper radar role extraction** — resolution raised from 28.9% to 54.2%, then a vocabulary
  pass and full database re-extract. `np%` leads now stand at 528, up from 405.
- **Lead routing columns** (commit `18e01f7`) — `offer`, `trigger_type`, `buyer_level` and
  `country` added to `leads` and backfilled. Groundwork for the Mystrika push service.

**Not yet built**
- Outreach layer (email via Mystrika, WhatsApp via PayPerWA, replies into Chatwoot).
- Optional VoIP dialer webhooks (Exotel/Twilio) to fill call duration / recording IDs.

See [`jd-lead-scrapping/CLAUDE.md`](jd-lead-scrapping/CLAUDE.md) and
[`jd-lead-scrapping/memory.md`](jd-lead-scrapping/memory.md) for the detailed handoff log and
verified system facts.
