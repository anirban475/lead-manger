# ACTION-016 — Deploy the expanded CSV import fields

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Production app on VPS: `/opt/telecaller-app` (container `telecaller-app`, port 3020)

## ⚠️ Coexistence — a parallel run may be active

The newspaper session works in this same checkout. All ACTION-011 rules apply:

- **Stay on `main`.** Never create or switch branches.
- **Never** `git add -A`, `git commit -a`, `git stash`, `git reset`,
  `git checkout .`, `git restore` or `git clean`.
- If the tree is dirty with `jd-lead-newspaper/` changes, that is the other
  run's work — **leave it exactly as it is**.
- **This task commits nothing.** It copies files and rebuilds one container.
- Do not touch `jd-lead-newspaper/` or `actions/ACTION-012*` / `ACTION-013*`.

The rebuild affects only the `telecaller-app` container — not `shared-postgres`,
not the newspaper cron or any sweep in progress.

## Why this exists

`28dd795` is merged to `main`: the bulk CSV import now maps **11** fields
instead of 6, adding company website, industry, job description, role titles and
a source label. The running container was built before that commit, so the
import wizard still shows only the old six. This takes `main` to the container.

The database grant for the four new columns (`company_website`, `industry`,
`job_description`, `role_titles`) has **already been applied** by Claude. Do not
run any SQL.

Three files differ between `main` and production, already confirmed:

```
telecaller-app/lib/csv.ts
telecaller-app/components/CsvUploadModal.tsx
telecaller-app/actions/bulkCreateLeads.ts
```

## Step 1 — report only, no changes

1. `git -C /root/projects/lead-manger rev-parse --abbrev-ref HEAD`,
   `git log --oneline -1`, and `git status -s` (report it, do not clean it).
2. `docker ps --filter name=telecaller-app --format "{{.Status}}"`
3. `grep -c "key: '" /opt/telecaller-app/lib/csv.ts` (expected `6` before deploy)
4. The full output of:
   ```
   diff -rq /root/projects/lead-manger/telecaller-app /opt/telecaller-app \
     -x node_modules -x .next -x .env -x next-env.d.ts -x .git -x .env.example -x '*.bak' -x '*.bak.*' -x tsconfig.tsbuildinfo
   ```

If item 4 lists any file other than the three above, **stop and report**.

Stop after reporting. Do not write anything yet.

## Step 2 — deploy

Only if Step 1 matched.

1. Back up the three production files, keeping timestamps:
   ```
   cd /opt/telecaller-app
   cp -p lib/csv.ts                     lib/csv.ts.bak.action016
   cp -p components/CsvUploadModal.tsx  components/CsvUploadModal.tsx.bak.action016
   cp -p actions/bulkCreateLeads.ts     actions/bulkCreateLeads.ts.bak.action016
   ```
2. Copy the three files from the repo:
   ```
   S=/root/projects/lead-manger/telecaller-app
   D=/opt/telecaller-app
   cp "$S/lib/csv.ts"                    "$D/lib/csv.ts"
   cp "$S/components/CsvUploadModal.tsx" "$D/components/CsvUploadModal.tsx"
   cp "$S/actions/bulkCreateLeads.ts"    "$D/actions/bulkCreateLeads.ts"
   ```
3. Rebuild and restart, from `/opt/telecaller-app`:
   ```
   docker compose up -d --build
   ```
4. Wait ~10 seconds, then run and paste the real output of each, with exit codes:
   ```
   grep -c "key: '" /opt/telecaller-app/lib/csv.ts
   grep -c "required: true" /opt/telecaller-app/lib/csv.ts
   grep -c "\$15" /opt/telecaller-app/actions/bulkCreateLeads.ts
   docker ps --filter name=telecaller-app --format "{{.Status}}"
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3020/login
   ```

The Docker build runs `next build`, which type-checks. **If the build fails**,
paste the failing output, restore the three `.bak.action016` backups, re-run
`docker compose up -d --build`, and stop.

## Step 3 — report and stop

Post the Step 2 output and stop. **Commit nothing.** Claude runs the live checks.

## Rules for this task

- Only the three named files may change in `/opt/telecaller-app`.
- The only docker command allowed is `docker compose up -d --build` from
  `/opt/telecaller-app`. No `down`, no volume removal, do not touch
  `shared-postgres`.
- **Do not connect to the database.** No psql — the grant is already applied.
- Do not touch `.env`; never print a secret.
- Do not commit, push, branch, or merge.
- One step per reply. Finish a step, report, and wait.

## Acceptance

1. `grep -c "key: '" /opt/telecaller-app/lib/csv.ts` prints `11`.
2. `grep -c "required: true" /opt/telecaller-app/lib/csv.ts` prints `2`.
3. `grep -c "\$15" /opt/telecaller-app/actions/bulkCreateLeads.ts` prints at
   least `1` (the 15-placeholder INSERT arrived).
4. `docker ps --filter name=telecaller-app` shows the container `Up`.
5. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3020/login` prints `200`.
6. `git status -s` still shows any pre-existing `jd-lead-newspaper/` changes,
   untouched and uncommitted.
