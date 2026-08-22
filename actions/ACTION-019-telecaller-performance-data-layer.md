# ACTION-019 — Telecaller performance data layer

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

There are 1,025 scored calls sitting in the `telecaller_coaching` database. Every
one has a call score, an objection handling score, a talk ratio and a summary,
written by the hourly n8n ingestion workflow.

None of it is visible to anyone. The only way a telecaller or a manager sees any
of it is the Saturday PDF, which arrives once a week, per person, by Slack DM. If
Bhratti's objection handling collapses on a Tuesday, nobody knows until Saturday.

The cockpit at leads.amatec.in is the obvious place to show it, but the app
connects to the `leads` database and the scores live in `telecaller_coaching`. A
Postgres connection is bound to one database, so the app currently cannot reach
the data at all.

This brief builds the data layer only. No page, no UI, no route. Just the second
connection, the queries, and a script that proves the numbers come out right.
The page is a separate brief that depends on this one.

## Prep already done by Claude (do not redo)

On 22 Aug 2026 the following was applied directly to the live
`telecaller_coaching` database. It is done. Do not re-apply it by hand, and do
not assume it is missing:

- `agents.app_user_email TEXT` added, plus a partial unique index on it
- backfilled: `anirban_sinha` to `anirban@amatec.in`, `bhratti_raval` to
  `bhratti@amatec.in`, `harsha_ahir` to `paherwarharsha@gmail.com`
- `GRANT CONNECT` on the database, `GRANT USAGE` on schema public, and
  `GRANT SELECT` on `agents`, `calls`, `chat_messages`, all to `leads_user`

`leads_user` is the role the cockpit already connects as, so it can now read the
coaching database with no new credential anywhere.

## Step 1 — report only, no changes

Read and report:

1. `git -C /root/projects/lead-manger status --short` and
   `git -C /root/projects/lead-manger log --oneline -3`
2. The full contents of `telecaller-app/lib/db.ts`
3. The output of:
   `docker exec shared-postgres psql -U admin -d telecaller_coaching -At -F'|' -c "select id,name,folder_name,app_user_email from agents order by id"`
4. Whether `pg` is already in `telecaller-app/package.json` dependencies, and its
   version
5. The environment variable NAMES defined for the `telecaller-app` service in
   `telecaller-app/docker-compose.yml`

Report key and variable NAMES only. Never print a value, not even partially, not
even a hostname, not even the first few characters.

Stop after reporting. Do not write anything yet.

## Step 2 — migration record file

Create `telecaller-app/sql/02_agents_app_user_email.sql`.

This file is the reproducible record of the prep above, so a fresh database
rebuild lands in the same state. It must be idempotent: `ADD COLUMN IF NOT
EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`, `UPDATE` statements matched on
`folder_name`, and the three `GRANT` statements.

Match the existing house style in `telecaller-app/sql/01_brand_eligibility.sql`.

Then run the file once against the live database to prove it is idempotent:

```
docker exec -i shared-postgres psql -U admin -d telecaller_coaching < telecaller-app/sql/02_agents_app_user_email.sql
```

Paste the real output. It should report `ALTER TABLE`, `CREATE INDEX`,
`UPDATE 1` three times and `GRANT` three times, changing nothing, because the
work is already applied.

## Step 3 — second connection pool

Create `telecaller-app/lib/coachingDb.ts`.

Requirements:

- Exports `coachingPool` and `coachingQuery<T>(text, params)`, mirroring the
  singleton shape already used in `lib/db.ts` including the `globalThis` reuse
  guard for dev hot reloads
- Connection string resolution, in this order: use
  `process.env.COACHING_DATABASE_URL` if it is set, otherwise derive it from
  `process.env.DATABASE_URL` by replacing the database name in the URL path with
  `telecaller_coaching`, leaving host, port, user and password untouched
- `max: 5`, `idleTimeoutMillis: 30_000`
- Throw a clear error if neither variable is available

Do not modify `lib/db.ts`. Do not log, print, echo or paste any connection
string, in code or in your reply, not even redacted.

## Step 4 — queries module

Create `telecaller-app/lib/coachingQueries.ts`. TypeScript, typed return rows, no
`any`.

Required exports:

| Function | Returns |
|---|---|
| `listAgents()` | id, name, folder_name, app_user_email |
| `getAgentByEmail(email)` | one agent row or null |
| `getScorecard(agentId, from, to)` | calls, avg_score, avg_objection, avg_agent_talk_share, tone counts |
| `getDailySeries(agentId, from, to)` | day, calls, avg_score, avg_objection |
| `getLeaderboard(from, to)` | per agent: agent_id, name, calls, avg_score, avg_objection, avg_talk_share |
| `getTopCalls(agentId, from, to, limit)` | id, call_time, customer_name, lead_phone, call_score, summary |
| `getBottomCalls(agentId, from, to, limit)` | same shape as getTopCalls |
| `getIssueCounts(agentId, from, to, limit)` | key_issues text and count, descending |

Rules that apply to every query:

- Where `agentId` is null, aggregate across all agents. Where it is set, scope to
  that agent. Never return another agent's rows when it is set.
- Exclude junk rows where `analysis->>'talk_ratio'` is `'0/0'`, `'100/0'` or
  `'0/100'`. Exclude them from results. Never delete them.
- Compute talk share only on rows matching `analysis->>'talk_ratio' ~
  '^[0-9]+/[0-9]+$'`, as `split_part(analysis->>'talk_ratio','/',1)::numeric`.
  A lower agent share is better, so do not invert it.
- Every value parameterised with `$1`, `$2` and so on. No string interpolation of
  dates, ids or limits into SQL, anywhere, for any reason.
- `getIssueCounts` returns the raw stored strings. Do not attempt to group,
  normalise or clean them. That is a separate brief and guessing at it here will
  produce wrong buckets.

Explicit non-goals for this step: no caching, no React, no server actions, no
route handlers.

## Step 5 — acceptance script

Create `telecaller-app/tools/perf-check.mjs`.

- Plain Node ESM. Use only `pg`, which is already a dependency. Add no packages.
- Calls every function exported in Step 4 for a 90 day window ending today,
  once with `agentId` null and once scoped to Bhratti Raval's agent id, resolved
  by `app_user_email = 'bhratti@amatec.in'` rather than hardcoded
- Prints each result as a labelled block, readable in a Slack paste
- Exits `0` when every query returns without error AND the leaderboard contains
  at least one agent with more than 900 calls
- Exits `1` otherwise, printing the name of the query that failed and its error

Run it once from `/root/projects/lead-manger/telecaller-app` and paste the real
output in full. Not a summary of the output. Not a description of what it
printed. The actual text.

## Step 6 — commit

Only after the Step 5 output is posted and looks right.

Another session is pushing to this repo every few minutes. So, in this order:

1. `git pull --rebase origin main`
2. Commit exactly these four new files, nothing else
3. Push to `origin main`
4. Report the commit hash and the output of `git status --short`

If the rebase reports a conflict in any file, stop and report it. Do not resolve
it.

## Step 7 — merge and clean up

Claude does this, not Antigravity, and only after Step 6 has been verified
independently against GitHub.

## Rules for this task

- Work only inside `/root/projects/lead-manger/telecaller-app`. Touch nothing
  else on the VPS.
- Do not create, edit or delete anything under the repo root `actions/`,
  `sql/migrations/`, `tools/`, or the root `README.md`. Another session owns
  those directories right now and is actively pushing to them.
- Do not modify `lib/db.ts`, `lib/auth.ts`, `lib/queries.ts`,
  `app/(app)/stats/page.tsx`, `docker-compose.yml`, `Dockerfile` or
  `package.json`.
- Do not create any `.tsx` file. There is no UI in this brief. If you find
  yourself writing a React component, you have misread the scope, so stop and
  say so.
- Do not rebuild, restart, redeploy or `docker compose up` the `telecaller-app`
  container. Another session's unfinished work is in the working copy and a
  deploy right now would ship it to leads.amatec.in.
- Do not `DELETE` or `DROP` anything in any database. The junk talk ratio rows
  are excluded by query, never removed.
- Report key, variable and credential NAMES only. Never a value, not even
  partially.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when `node tools/perf-check.mjs`, run from
`/root/projects/lead-manger/telecaller-app`, prints a leaderboard row for
**Bhratti Raval** with more than 900 calls and an average call score between
4.0 and 5.0, exits `0`, and the four new files are pushed to `main`.
