# ACTION-018 — Deploy the brand gate and the CSV preview together

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Production app on VPS: `/opt/telecaller-app` (container `telecaller-app`, port 3020)

## Why this exists — and why it is one rebuild, not two

Two separate pieces of work are merged to `main` and neither is deployed:

- **`d378e03`** — brand eligibility gate on the queue (another session's work).
  `getQueue`/`getFollowups` now take the caller's email and filter on
  `leads.eligible_brands` against `app_users.brand`, read at query time so a
  reassignment applies immediately and a stale cookie cannot leak leads. Admins
  bypass. Its SQL migration is **already applied** to the live database.
- **`4e96d5f`** — the CSV import preview table now shows all eleven mapped
  fields instead of five.

Anirban asked for both to go out in a single container rebuild rather than two
restarts. That is what this task does.

**The brand gate has been verified safe before deploy.** Against live data the
gated query returns **478 leads for Bhratti**, identical to the current ungated
478, and there are **0 amatec-eligible leads** in the queue set. So the gate
changes nothing today and exists to stop amatec leads appearing once they get
phone numbers. It cannot empty the queue.

## Five files differ, already confirmed

```
telecaller-app/lib/queries.ts                       # brand gate
telecaller-app/app/(app)/queue/page.tsx             # brand gate
telecaller-app/app/(app)/followups/page.tsx         # brand gate
telecaller-app/components/CsvUploadModal.tsx        # CSV preview
telecaller-app/README.md                            # docs
```

**Do NOT copy `telecaller-app/sql/`.** Those are migration files, already
applied to the database. The container has no use for them and must not run
them.

## ⚠️ Coexistence

Other sessions share this checkout.

- **Stay on `main`.** Never create or switch branches.
- **Never** `git add -A`, `git commit -a`, `git stash`, `git reset`,
  `git checkout .`, `git restore` or `git clean`.
- **This task commits nothing.** It copies files and rebuilds one container.
- Leave **all** pre-existing modified files alone, in any directory.
- Do not touch `jd-lead-newspaper/` or `actions/ACTION-012*` / `ACTION-013*`.
- The rebuild affects only the `telecaller-app` container — not
  `shared-postgres`, not the newspaper cron.

## Step 1 — report only, no changes

1. `git -C /root/projects/lead-manger rev-parse --abbrev-ref HEAD`,
   `git log --oneline -2`, and `git status -s` (report it, do not clean it).
2. `docker ps --filter name=telecaller-app --format "{{.Status}}"`
3. Baselines, all expected `0` before deploy:
   ```
   grep -c BRAND_GATE /opt/telecaller-app/lib/queries.ts
   grep -c "Role Titles" /opt/telecaller-app/components/CsvUploadModal.tsx
   ```
4. The full output of:
   ```
   diff -rq /root/projects/lead-manger/telecaller-app /opt/telecaller-app \
     -x node_modules -x .next -x .env -x next-env.d.ts -x .git -x .env.example -x '*.bak' -x '*.bak.*' -x tsconfig.tsbuildinfo
   ```

Expect the five files plus `Only in ...: sql`. If anything else appears, **stop
and report**.

Stop after reporting. Do not write anything yet.

## Step 2 — deploy

Only if Step 1 matched.

1. Back up the five production files, keeping timestamps:
   ```
   cd /opt/telecaller-app
   cp -p lib/queries.ts                          lib/queries.ts.bak.action018
   cp -p "app/(app)/queue/page.tsx"              "app/(app)/queue/page.tsx.bak.action018"
   cp -p "app/(app)/followups/page.tsx"          "app/(app)/followups/page.tsx.bak.action018"
   cp -p components/CsvUploadModal.tsx           components/CsvUploadModal.tsx.bak.action018
   cp -p README.md                               README.md.bak.action018
   ```
2. Copy the five files (and **only** those five):
   ```
   S=/root/projects/lead-manger/telecaller-app
   D=/opt/telecaller-app
   cp "$S/lib/queries.ts"                   "$D/lib/queries.ts"
   cp "$S/app/(app)/queue/page.tsx"         "$D/app/(app)/queue/page.tsx"
   cp "$S/app/(app)/followups/page.tsx"     "$D/app/(app)/followups/page.tsx"
   cp "$S/components/CsvUploadModal.tsx"    "$D/components/CsvUploadModal.tsx"
   cp "$S/README.md"                        "$D/README.md"
   ```
3. Rebuild and restart, from `/opt/telecaller-app`:
   ```
   docker compose up -d --build
   ```
4. Wait ~10 seconds, then run and paste the real output of each, with exit codes:
   ```
   grep -c BRAND_GATE /opt/telecaller-app/lib/queries.ts
   grep -c "Role Titles" /opt/telecaller-app/components/CsvUploadModal.tsx
   grep -c "getQueue(session.email" "/opt/telecaller-app/app/(app)/queue/page.tsx"
   docker ps --filter name=telecaller-app --format "{{.Status}}"
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3020/login
   ls /opt/telecaller-app/sql 2>&1
   ```

The last one must report **no such file or directory** — `sql/` must not have
been copied.

The Docker build runs `next build`, which type-checks. **If the build fails**,
paste the failing output, restore all five `.bak.action018` backups, re-run
`docker compose up -d --build`, and stop. This is the queue — the telecaller's
main screen — so a failed build must be rolled back, not left broken.

## Step 3 — report and stop

Post the Step 2 output and stop. **Commit nothing.** Claude runs the live checks.

## Rules for this task

- Only the five named files may change in `/opt/telecaller-app`. Do not copy
  `sql/`, `node_modules/` or anything else.
- The only docker command allowed is `docker compose up -d --build` from
  `/opt/telecaller-app`. No `down`, no volume removal, do not touch
  `shared-postgres`.
- **Do not connect to the database.** The migration is already applied.
- Do not touch `.env`; never print a secret.
- Do not commit, push, branch or merge.
- One step per reply. Finish a step, report, and wait.

## Acceptance

1. `grep -c BRAND_GATE /opt/telecaller-app/lib/queries.ts` prints at least `1`.
2. `grep -c "Role Titles" /opt/telecaller-app/components/CsvUploadModal.tsx`
   prints at least `1`.
3. `grep -c "getQueue(session.email" .../queue/page.tsx` prints at least `1`.
4. `docker ps` shows the container `Up`.
5. `curl .../login` prints `200`.
6. `/opt/telecaller-app/sql` does **not** exist.
