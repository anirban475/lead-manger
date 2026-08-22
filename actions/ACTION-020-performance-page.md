# ACTION-020 — Performance page, manager role and filters

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

Depends on ACTION-019, shipped in `c646d3f`. Read
`telecaller-app/README.md` section "Call quality lives in a second database"
before starting. It carries the traps.

## Why this exists

ACTION-019 made 1,025 scored calls readable from the cockpit. Nothing renders
them. A telecaller still finds out how they are doing once a week, in a PDF, on
Saturday, and Anirban has no way at all to see the team side by side.

The goal is not a pretty chart. It is that a manager can open one page on a
Monday, see that objection handling sat at 3.32 against a target of 6, see which
days it collapsed, and open the three worst calls behind it. That is the
difference between watching performance and handling it.

## Step 1 — report only, no changes

Read and report:

1. Full contents of `telecaller-app/app/(app)/layout.tsx`
2. Full contents of `telecaller-app/app/(app)/stats/page.tsx`
3. The CSS class names available in `telecaller-app/app/globals.css` that are
   used for layout and cards. List the names only, not the rules.
4. The `dependencies` block of `telecaller-app/package.json`
5. `git -C /root/projects/lead-manger log --oneline -3`

Stop after reporting. Do not write anything yet.

## Step 2 — manager role in auth

Modify `telecaller-app/lib/auth.ts`. This is the one file outside the new route
you may touch, and only for this:

- Add `export function canSeeTeam(role: string): boolean` returning true for
  `'admin'` and `'manager'`, false otherwise
- Add `export async function requireTeamView(): Promise<Session>` mirroring the
  existing `requireAdmin()` but accepting both `'admin'` and `'manager'`, and
  re-reading the role from `app_users` at query time rather than trusting the
  cookie, exactly as `requireAdmin()` already does
- Do not change `requireAdmin()`, `verifyCredentials()`, `createSession()`,
  `getSession()` or `destroySession()`

Do not add a role CHECK constraint to the database. `app_users.role` is
deliberately unconstrained.

Paste the diff.

## Step 3 — the page

Create `telecaller-app/app/(app)/performance/page.tsx`. Server component,
`export const dynamic = 'force-dynamic'`.

### Scope rules, and these are the security contract

- Read the session with `getSession()`. Resolve the caller's own agent via
  `getAgentByEmail(session.email)`.
- `admin` and `manager` see the whole team and get an agent picker.
- `caller` sees only their own calls. No picker, no leaderboard, no other name
  anywhere on the page.
- **A `caller` who hand-edits the URL to `?agent=3` must still see only their
  own data.** Resolve the effective agent id on the server from the session
  first, and only honour the `agent` search param when `canSeeTeam(role)` is
  true. Never pass a client-supplied id straight into a query.

### Filters, all held in the URL so a link can be shared

- `from` and `to`, ISO dates. Default: the last 30 days.
- `agent`, an agent id or `all`. Ignored for callers.
- `compare`, one of `off`, `previous`, or an agent id.
- Preset buttons for 7 days, 30 days, this month, and a custom range.
- Changing a filter is a plain link or a form GET that updates the URL. No
  client-side state library, no `use client` unless a control genuinely needs it.

### Panels, in this order

1. Four scorecards: calls, average score, average objection handling, average
   agent talk share. Each shows the delta against the previous equal-length
   period, green for better, red for worse. Talk share is better when lower, so
   do not colour it the wrong way.
2. Daily series: calls per day as bars, average score per day as a line.
3. Objection handling per day with a dashed target line at 6.
4. Leaderboard table, team scope only, ranked. Hidden entirely for callers.
5. Best 3 and worst 3 calls, showing customer name or lead phone, score, and
   summary.
6. Top issues from `getIssueCounts`, with a visible one-line caveat that these
   are raw strings from the analysis and near-duplicates are not yet merged.

### Constraints on how it is built

- **Add no npm packages.** Draw every chart as inline SVG. No recharts, no
  chart.js, no d3. Do not modify `package.json`.
- Reuse the existing classes from `globals.css` that `stats/page.tsx` uses:
  `topbar`, `content`, `stack`, `card`, `pad`, `section-title`, `badge`,
  `muted`. Match that page's visual language rather than inventing a new one.
- Mobile first. Telecallers will open this on a phone. Any table or chart wider
  than the screen scrolls inside its own container, and the page body never
  scrolls sideways.
- `talk_ratio` must be labelled as an estimate wherever it appears. It is the
  model's guess from a transcript, not a measurement.
- Show an honest empty state when an agent has no calls in the range. Harsha
  Ahir has zero calls and must not render as a crash or as zeros pretending to
  be data.

## Step 4 — nav link

Add a `Performance` link to the nav in `telecaller-app/app/(app)/layout.tsx`,
matching the existing link pattern exactly. Change nothing else in that file.

## Step 5 — build

Run, from `/root/projects/lead-manger/telecaller-app`:

```
npm run build
node tools/perf-check.mjs
```

Paste the real output of both, including the exit codes. Not a summary.

If the build fails, fix it and run it again. Report both the failure and the
fix.

## Step 6 — commit

Only after Step 5 output is posted and both commands exit 0.

1. `git pull --rebase origin main`
2. Commit only the files this brief names
3. Push to `origin main`
4. Report the commit hash and `git status --short`

## Step 7 — deploy

**Do not do this step.** Claude runs the container rebuild after verifying
Step 6 independently. Stop after Step 6 and say so.

## Rules for this task

- Work only inside `/root/projects/lead-manger/telecaller-app`.
- Files you may create or modify, and nothing else:
  `app/(app)/performance/page.tsx`, any new files under
  `app/(app)/performance/`, `lib/auth.ts` for Step 2 only, and
  `app/(app)/layout.tsx` for the nav link only.
- Do not modify `lib/db.ts`, `lib/coachingDb.ts`, `lib/coachingQueries.ts`,
  `lib/queries.ts`, `app/(app)/stats/page.tsx`, `package.json`,
  `docker-compose.yml` or `Dockerfile`.
- Do not touch the repo root `actions/`, `sql/migrations/`, `tools/` or
  `README.md`.
- Do not rebuild, restart or redeploy the `telecaller-app` container.
- Do not `DELETE` or `DROP` anything in any database. This page is read only.
- Do not add any npm package for any reason. If a chart seems to need one, draw
  it in SVG instead.
- Report key and variable NAMES only. Never a value.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when `npm run build` exits 0, `node tools/perf-check.mjs` still exits 0,
the page renders for an `admin` with a leaderboard containing Bhratti Raval, a
`caller` session cannot reach another agent's rows by editing the `agent` search
param, and the work is pushed to `main`.
