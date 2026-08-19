# ACTION-008 — Deploy the user-management branch to production

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Production app on VPS: `/opt/telecaller-app` (container `telecaller-app`, host port 3020)

## Why this exists

ACTION-007 is committed and pushed as branch `feat/user-management` (`9f8f0e4`)
but is **not merged**. Anirban wants it verified on the live site *before* it
goes into `main`, so this deploy takes the **branch**, not `main`, to the
container. Claude merges to `main` only after the live checks pass.

That means production will briefly run un-merged code. That is intended. If the
live checks fail, the rollback is the backups taken in Step 2.

The database is already prepared (ACTION-007): `app_users.is_active` exists,
grants are in place, and `anirban@amatec.in` is `role='admin'`. **Do not run
psql. Do not connect to the database.**

## Step 1 — report only, no changes

Read and report:

1. `git -C /root/projects/lead-manger rev-parse --abbrev-ref HEAD` and
   `git -C /root/projects/lead-manger log --oneline -1`
2. `docker ps --filter name=telecaller-app --format "{{.Status}}"`
3. `ls /opt/telecaller-app/app/\(app\)/users 2>&1` (expected: no such directory)
4. With the clone on `feat/user-management`, the full output of:
   ```
   diff -rq /root/projects/lead-manger/telecaller-app /opt/telecaller-app \
     -x node_modules -x .next -x .env -x next-env.d.ts -x .git -x .env.example -x '*.bak' -x '*.bak.*' -x tsconfig.tsbuildinfo
   ```

Expect exactly the ten ACTION-007 files. If anything else appears, **stop and
report**. Do not deploy.

Report key names only where credentials are involved. Never print a password or
a hash.

Stop after reporting. Do not write anything yet.

## Step 2 — deploy the branch

Only if Step 1 matched.

1. Make sure the clone is on the branch:
   ```
   cd /root/projects/lead-manger && git checkout feat/user-management && git pull --ff-only
   ```
2. Back up the four production files that already exist, keeping timestamps:
   ```
   cd /opt/telecaller-app
   cp -p lib/auth.ts                 lib/auth.ts.bak.action008
   cp -p components/AppNav.tsx       components/AppNav.tsx.bak.action008
   cp -p "app/(app)/layout.tsx"      "app/(app)/layout.tsx.bak.action008"
   cp -p deploy/schema.sql           deploy/schema.sql.bak.action008
   ```
3. Create the new route directory and copy all ten files from the branch:
   ```
   mkdir -p "/opt/telecaller-app/app/(app)/users"
   S=/root/projects/lead-manger/telecaller-app
   D=/opt/telecaller-app
   cp "$S/lib/auth.ts"                  "$D/lib/auth.ts"
   cp "$S/lib/users.ts"                 "$D/lib/users.ts"
   cp "$S/actions/createUser.ts"        "$D/actions/createUser.ts"
   cp "$S/actions/resetUserPassword.ts" "$D/actions/resetUserPassword.ts"
   cp "$S/actions/setUserActive.ts"     "$D/actions/setUserActive.ts"
   cp "$S/components/UsersAdmin.tsx"    "$D/components/UsersAdmin.tsx"
   cp "$S/components/AppNav.tsx"        "$D/components/AppNav.tsx"
   cp "$S/app/(app)/layout.tsx"         "$D/app/(app)/layout.tsx"
   cp "$S/app/(app)/users/page.tsx"     "$D/app/(app)/users/page.tsx"
   cp "$S/deploy/schema.sql"            "$D/deploy/schema.sql"
   ```
4. Rebuild and restart, from `/opt/telecaller-app`:
   ```
   docker compose up -d --build
   ```
5. Wait ~10 seconds, then run and paste the real output of all four:
   ```
   grep -c "requireAdmin" /opt/telecaller-app/lib/auth.ts
   grep -c "created_at::text" /opt/telecaller-app/lib/users.ts
   docker ps --filter name=telecaller-app --format "{{.Status}}"
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3020/login
   ```

Paste each with its exit code. The Docker build runs `next build`, which
type-checks. **If the build fails**, paste the failing output, restore the four
`.bak.action008` backups, remove `/opt/telecaller-app/app/(app)/users` and the
three new action files plus `lib/users.ts` and `components/UsersAdmin.tsx`,
re-run `docker compose up -d --build`, and stop.

## Step 3 — report and wait

Do **not** commit anything for this task and do **not** merge. Post the Step 2
output and stop. Claude runs the live checks and does the merge.

## Rules for this task

- Only the ten files listed above may change in `/opt/telecaller-app`, plus the
  one new `app/(app)/users/` directory. Nothing else may be edited or deleted.
- The only docker command allowed is `docker compose up -d --build` from
  `/opt/telecaller-app`. Do not run `docker compose down`, do not remove volumes,
  do not touch `shared-postgres`.
- **Do not connect to the database.** No psql, no writes.
- Do not open, edit, copy or print `/opt/telecaller-app/.env`. Never print a
  password or a hash, not even partially.
- Do not modify any file under `telecaller-app/` in the git repo, and do not
  merge the branch.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when, with pasted output:

1. `grep -c "requireAdmin" /opt/telecaller-app/lib/auth.ts` prints at least `1`.
2. `grep -c "created_at::text" /opt/telecaller-app/lib/users.ts` prints `1`.
3. `docker ps --filter name=telecaller-app --format "{{.Status}}"` shows `Up`.
4. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3020/login` prints `200`.
