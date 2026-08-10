# ACTION-002 — Deploy the invalid-number filter to production

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Production app on VPS: `/opt/telecaller-app` (container `telecaller-app`, host port 3020)

## Why this exists

ACTION-001 is merged to `main` as `8c7cddb`, but the running app has not been
rebuilt, so nothing has changed for the telecaller. Production is still serving
**76 leads**, including the **31 dead numbers** the fix exists to remove. The
code is only worth what is deployed, so this task takes `main` to the container.

ACTION-001 deliberately forbade touching `/opt/telecaller-app` and running
`docker`. **This brief authorises both, narrowly**, for exactly one file and one
rebuild. Anirban asked for this deploy explicitly.

Exactly one file differs between `main` and production, already confirmed:

```
/root/projects/lead-manger/telecaller-app/lib/queries.ts   <->   /opt/telecaller-app/lib/queries.ts
```

Nothing else. If your Step 1 finds any other file differing, stop and report it
rather than deploying.

## Step 1 — report only, no changes

With `/root/projects/lead-manger` already on `main` at `8c7cddb`, read and
report:

1. `git -C /root/projects/lead-manger log --oneline -1`
2. `grep -c NOT_INVALID_NUMBER /opt/telecaller-app/lib/queries.ts` (expected `0`
   before deploy, because production still has the old file)
3. `docker ps --filter name=telecaller-app --format "{{.Status}}"`
4. The full output of:
   ```
   diff -rq /root/projects/lead-manger/telecaller-app /opt/telecaller-app \
     -x node_modules -x .next -x .env -x next-env.d.ts -x .git -x .env.example -x '*.bak' -x '*.bak.*'
   ```

If item 4 lists any file other than `lib/queries.ts`, **stop and report**. Do
not deploy.

Report key names only where credentials are involved. Never print a value, not
even partially.

Stop after reporting. Do not write anything yet.

## Step 2 — deploy

Only if Step 1 showed `lib/queries.ts` as the single difference.

1. Back up the current production file, keeping its timestamp:
   ```
   cp -p /opt/telecaller-app/lib/queries.ts /opt/telecaller-app/lib/queries.ts.bak.action002
   ```
2. Copy the merged version into production:
   ```
   cp /root/projects/lead-manger/telecaller-app/lib/queries.ts /opt/telecaller-app/lib/queries.ts
   ```
3. Rebuild and restart the container, from `/opt/telecaller-app`:
   ```
   docker compose up -d --build
   ```
4. Wait ~10 seconds, then run and paste the real output of all three:
   ```
   grep -c NOT_INVALID_NUMBER /opt/telecaller-app/lib/queries.ts
   docker ps --filter name=telecaller-app --format "{{.Status}}"
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3020/login
   ```

Paste the real output of each with its exit code. Not a summary. If
`docker compose up -d --build` fails, paste the failing output, restore the
backup from step 1, and stop.

## Step 3 — commit the deploy record

Only after Step 2 output is posted and the checks passed:

- Append an entry to `actions/deploy-log.md` in `/root/projects/lead-manger`
  (create the file if it does not exist) recording: the date, `ACTION-002`, the
  commit deployed (`8c7cddb`), the file deployed, and the three verification
  outputs from Step 2.
- Commit it to `main` and push to `origin`.
- Report the commit hash.

## Rules for this task

- The **only** file you may change in `/opt/telecaller-app` is `lib/queries.ts`.
  Nothing else in that directory may be edited, moved or deleted.
- The **only** docker command you may run is `docker compose up -d --build` from
  `/opt/telecaller-app`. Do not run `docker compose down`, do not remove volumes,
  do not touch the `shared-postgres` container.
- Do not open, edit, copy or print `/opt/telecaller-app/.env` or any credential
  file. Never print a secret value, not even partially.
- Do not connect to the database. No `psql`, no migrations, no writes. Claude
  verifies the data side separately.
- Do not modify any file in `telecaller-app/` in the git repo. The code is
  already merged and correct; this task only moves it and records it.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when all three hold, with pasted output:

1. `grep -c NOT_INVALID_NUMBER /opt/telecaller-app/lib/queries.ts` prints `3`
   and exits `0` (one declaration plus two usages).
2. `docker ps --filter name=telecaller-app --format "{{.Status}}"` shows the
   container `Up`.
3. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3020/login` prints
   `200`.

and the deploy-log entry is pushed to `main`.
