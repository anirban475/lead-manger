# ACTION-004 — Deploy the Last Outcome filter to production

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Production app on VPS: `/opt/telecaller-app` (container `telecaller-app`, host port 3020)

## Why this exists

ACTION-003 is merged to `main` as `51393c4`, but the running app has not been
rebuilt. The telecaller still sees an "All Statuses" dropdown that filters an
invisible field, and still cannot filter the LAST OUTCOME column she actually
works from. This task takes `main` to the container.

This is the same shape as ACTION-002, which deployed cleanly. Three files differ
between `main` and production, already confirmed:

```
telecaller-app/components/CallSheet.tsx
telecaller-app/components/FilterBar.tsx
telecaller-app/lib/savedFilters.ts
```

**Do not copy `tsconfig.tsbuildinfo`.** It exists in the repo clone as a local
build artifact from a typecheck. It is gitignored and must not reach production.

## Step 1 — report only, no changes

With `/root/projects/lead-manger` on `main` at `51393c4`, read and report:

1. `git -C /root/projects/lead-manger log --oneline -1`
2. `grep -c lastOutcome /opt/telecaller-app/lib/savedFilters.ts` (expected `0`
   before deploy)
3. `docker ps --filter name=telecaller-app --format "{{.Status}}"`
4. The full output of:
   ```
   diff -rq /root/projects/lead-manger/telecaller-app /opt/telecaller-app \
     -x node_modules -x .next -x .env -x next-env.d.ts -x .git -x .env.example -x '*.bak' -x '*.bak.*'
   ```

If item 4 lists any file other than the three named above and
`tsconfig.tsbuildinfo`, **stop and report**. Do not deploy.

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — deploy

Only if Step 1 matched.

1. Back up the three current production files, keeping timestamps:
   ```
   cd /opt/telecaller-app
   cp -p components/CallSheet.tsx components/CallSheet.tsx.bak.action004
   cp -p components/FilterBar.tsx components/FilterBar.tsx.bak.action004
   cp -p lib/savedFilters.ts     lib/savedFilters.ts.bak.action004
   ```
2. Copy the merged versions into production (these three files only):
   ```
   cp /root/projects/lead-manger/telecaller-app/components/CallSheet.tsx   /opt/telecaller-app/components/CallSheet.tsx
   cp /root/projects/lead-manger/telecaller-app/components/FilterBar.tsx   /opt/telecaller-app/components/FilterBar.tsx
   cp /root/projects/lead-manger/telecaller-app/lib/savedFilters.ts        /opt/telecaller-app/lib/savedFilters.ts
   ```
3. Rebuild and restart, from `/opt/telecaller-app`:
   ```
   docker compose up -d --build
   ```
4. Wait ~10 seconds, then run and paste the real output of all four:
   ```
   grep -c lastOutcome /opt/telecaller-app/lib/savedFilters.ts
   grep -c "All Outcomes" /opt/telecaller-app/components/FilterBar.tsx
   docker ps --filter name=telecaller-app --format "{{.Status}}"
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3020/login
   ```

Paste the real output of each with its exit code. Not a summary. The Docker
build runs `next build`, which type-checks; if the build fails, paste the
failing output, restore the three backups from step 1, re-run
`docker compose up -d --build`, and stop.

## Step 3 — commit the deploy record

Only after Step 2 output is posted and the checks passed:

- Append an entry to `actions/deploy-log.md` recording: the date, `ACTION-004`,
  the commit deployed (`51393c4`), the three files deployed, and the four
  verification outputs from Step 2.
- Commit it to `main` and push to `origin`.
- Report the commit hash.

## Rules for this task

- The **only** files you may change in `/opt/telecaller-app` are the three named
  above. Nothing else in that directory may be edited, moved or deleted.
- Do not copy `tsconfig.tsbuildinfo` or `node_modules` into `/opt`.
- The **only** docker command you may run is `docker compose up -d --build` from
  `/opt/telecaller-app`. Do not run `docker compose down`, do not remove volumes,
  do not touch the `shared-postgres` container.
- Do not open, edit, copy or print `/opt/telecaller-app/.env` or any credential
  file. Never print a secret value, not even partially.
- Do not connect to the database. No `psql`, no writes.
- Do not modify any file under `telecaller-app/` in the git repo.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when all four hold, with pasted output:

1. `grep -c lastOutcome /opt/telecaller-app/lib/savedFilters.ts` prints `1`,
   exit `0`.
2. `grep -c "All Outcomes" /opt/telecaller-app/components/FilterBar.tsx` prints
   `1`, exit `0`.
3. `docker ps --filter name=telecaller-app --format "{{.Status}}"` shows `Up`.
4. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3020/login` prints
   `200`.

and the deploy-log entry is pushed to `main`.
