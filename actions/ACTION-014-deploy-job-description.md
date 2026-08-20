# ACTION-014 — Deploy the job-description change to production

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Production app on VPS: `/opt/telecaller-app` (container `telecaller-app`, port 3020)

## ⚠️ A parallel run is active in this same working copy

The newspaper session (`ACTION-012` / `ACTION-013`) is working in
`/root/projects/lead-manger` at the same time. The coexistence rules from
ACTION-011 still apply in full:

- **Stay on `main`.** Never create or switch branches.
- **Never** `git add -A`, `git add .`, `git commit -a`, `git stash`,
  `git reset`, `git checkout .`, `git restore` or `git clean`.
- If the tree is dirty with `jd-lead-newspaper/` changes, that is the other
  run's work. **Leave it exactly as it is** and carry on.
- This task commits **nothing**. It only copies files and rebuilds a container.

The rebuild affects only the `telecaller-app` container. It does not touch
`shared-postgres`, the newspaper cron, or any sweep in progress.

## Why this exists

`82d9499` is merged to `main`: the telecaller can now see `leads.job_description`
in the lead drawer and on the lead detail page. The running container was built
before that commit, so nothing has changed for Bhratti yet. This takes `main` to
the container.

Four files differ between `main` and production, already confirmed:

```
telecaller-app/lib/queries.ts
telecaller-app/components/LeadPanel.tsx
telecaller-app/app/(app)/leads/[company_key]/page.tsx
telecaller-app/deploy/schema.sql        # documentation only, no code path
```

## Step 1 — report only, no changes

1. `git -C /root/projects/lead-manger rev-parse --abbrev-ref HEAD`,
   `git -C /root/projects/lead-manger log --oneline -1`, and
   `git -C /root/projects/lead-manger status -s` (report it, do not clean it).
   Pull first with `git pull --ff-only origin main`; if that fails because the
   tree is dirty, say so and continue — do not clean.
2. `docker ps --filter name=telecaller-app --format "{{.Status}}"`
3. `grep -c job_description /opt/telecaller-app/lib/queries.ts` (expected `0`
   before deploy)
4. The full output of:
   ```
   diff -rq /root/projects/lead-manger/telecaller-app /opt/telecaller-app \
     -x node_modules -x .next -x .env -x next-env.d.ts -x .git -x .env.example -x '*.bak' -x '*.bak.*' -x tsconfig.tsbuildinfo
   ```

If item 4 lists any file other than the four above, **stop and report**.

Stop after reporting. Do not write anything yet.

## Step 2 — deploy

Only if Step 1 matched.

1. Back up the four production files, keeping timestamps:
   ```
   cd /opt/telecaller-app
   cp -p lib/queries.ts                        lib/queries.ts.bak.action014
   cp -p components/LeadPanel.tsx              components/LeadPanel.tsx.bak.action014
   cp -p "app/(app)/leads/[company_key]/page.tsx" "app/(app)/leads/[company_key]/page.tsx.bak.action014"
   cp -p deploy/schema.sql                     deploy/schema.sql.bak.action014
   ```
2. Copy the four files from the repo:
   ```
   S=/root/projects/lead-manger/telecaller-app
   D=/opt/telecaller-app
   cp "$S/lib/queries.ts"                          "$D/lib/queries.ts"
   cp "$S/components/LeadPanel.tsx"                "$D/components/LeadPanel.tsx"
   cp "$S/app/(app)/leads/[company_key]/page.tsx"  "$D/app/(app)/leads/[company_key]/page.tsx"
   cp "$S/deploy/schema.sql"                       "$D/deploy/schema.sql"
   ```
3. Rebuild and restart, from `/opt/telecaller-app`:
   ```
   docker compose up -d --build
   ```
4. Wait ~10 seconds, then run and paste the real output of all four, each with
   its exit code:
   ```
   grep -c job_description /opt/telecaller-app/lib/queries.ts
   grep -c "Job Description" /opt/telecaller-app/components/LeadPanel.tsx
   docker ps --filter name=telecaller-app --format "{{.Status}}"
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3020/login
   ```

The Docker build runs `next build`, which type-checks. **If the build fails**,
paste the failing output, restore the four `.bak.action014` backups, re-run
`docker compose up -d --build`, and stop.

## Step 3 — report and stop

Post the Step 2 output and stop. **Commit nothing.** Claude runs the live checks.

## Rules for this task

- Only the four named files may change in `/opt/telecaller-app`.
- The only docker command allowed is `docker compose up -d --build` from
  `/opt/telecaller-app`. No `down`, no volume removal, do not touch
  `shared-postgres`.
- **Do not connect to the database.** No psql.
- Do not touch `.env`; never print a secret.
- Do not touch `jd-lead-newspaper/`, `actions/ACTION-012*` or `actions/ACTION-013*`.
- Do not commit, do not push, do not branch.
- One step per reply. Finish a step, report, and wait.

## Acceptance

1. `grep -c job_description /opt/telecaller-app/lib/queries.ts` prints `2`.
2. `grep -c "Job Description" /opt/telecaller-app/components/LeadPanel.tsx`
   prints at least `1`.
3. `docker ps --filter name=telecaller-app` shows the container `Up`.
4. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3020/login` prints `200`.
5. `git status -s` still shows any pre-existing `jd-lead-newspaper/` changes,
   untouched and uncommitted.
