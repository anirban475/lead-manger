# ACTION-009 — Let an admin reset their own password

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`
Production app on VPS: `/opt/telecaller-app` (container `telecaller-app`, port 3020)

> Numbering note: two people are numbering briefs in this repo. `ACTION-006` and
> `ACTION-007-production-schedule.md` belong to the newspaper project and are
> still in flight. **Do not touch them.** This task is `telecaller-app/` only.

## Why this exists

ACTION-007 shipped the Users page. Both per-row buttons, *Reset password* and
*Deactivate*, are disabled on the signed-in admin's own row. Disabling
*Deactivate* is deliberate and must stay — an admin who deactivates themselves
locks everyone out of user management for good.

Disabling *Reset password* on your own row was over-cautious. An admin who wants
to change their own password currently cannot, and has to go to the database.
Anirban wants it enabled.

The server action already allows this: `actions/resetUserPassword.ts` is gated on
`requireAdmin()` only and has no self-check. **This is a UI-only change.**

## The one thing that will break this task

`setUserActive` **must keep refusing self-deactivation**, both in
`actions/setUserActive.ts` and via the disabled *Deactivate* button. Do not
"tidy" the two buttons into sharing one `disabled={self || isPending}`
expression, and do not remove the self-check in the action. Only the *Reset
password* button changes.

## Step 1 — report only, no changes

With the clone on `main`, read and report:

1. The full JSX of the two per-row buttons in
   `telecaller-app/components/UsersAdmin.tsx` (*Reset password* and
   *Deactivate/Reactivate*), with line numbers.
2. Confirm, quoting the line, that `telecaller-app/actions/resetUserPassword.ts`
   contains **no** self-check against the session email.
3. Confirm, quoting the line, that `telecaller-app/actions/setUserActive.ts`
   **does** contain its self-check.

Stop after reporting. Do not write anything yet.

## Step 2 — build

Modify **only** `telecaller-app/components/UsersAdmin.tsx`.

- On the **Reset password** button: change `disabled={self || isPending}` to
  `disabled={isPending}`, and change its `title` so the self case reads
  `Reset your own password` instead of `You cannot reset your own password here`.
- Leave the **Deactivate/Reactivate** button exactly as it is —
  `disabled={self || isPending}` and its existing title stay.
- Change nothing else. No server-action changes, no schema, no other files.

Then run from `/root/projects/lead-manger/telecaller-app` and paste the real
output of each with its exit code:

```
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```
(not `npx tsc` — that resolves to an unrelated package in this clone)

```
grep -n "disabled={self || isPending}" components/UsersAdmin.tsx
```
That grep must now return **exactly one** line, the Deactivate button.

## Step 3 — commit

- Branch `feat/admin-self-password-reset` off `main`, commit the one file, push
  with `-u`.
- Report branch, commit hash, and `git diff --name-only main..feat/admin-self-password-reset`
  (must be exactly `telecaller-app/components/UsersAdmin.tsx`).
- Do not merge.

## Step 4 — deploy the branch

Only after Claude approves Step 3.

```
cd /opt/telecaller-app
cp -p components/UsersAdmin.tsx components/UsersAdmin.tsx.bak.action009
cp /root/projects/lead-manger/telecaller-app/components/UsersAdmin.tsx /opt/telecaller-app/components/UsersAdmin.tsx
docker compose up -d --build
```

Then wait ~10s and paste, with exit codes:
```
grep -c "disabled={self || isPending}" /opt/telecaller-app/components/UsersAdmin.tsx
docker ps --filter name=telecaller-app --format "{{.Status}}"
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:3020/login
```

If the build fails, paste the output, restore `UsersAdmin.tsx.bak.action009`,
rebuild, and stop.

## Rules for this task

- Work only inside `/root/projects/lead-manger` and, in Step 4, the single named
  file in `/opt/telecaller-app`.
- The only docker command allowed is `docker compose up -d --build` from
  `/opt/telecaller-app`.
- **Do not connect to the database.** No psql.
- Do not touch `.env`; never print a password or hash.
- Do not touch `jd-lead-newspaper/` or the newspaper briefs.
- Do not merge to `main`. Claude merges.
- One step per reply. Finish a step, report, and wait.

## Acceptance

1. `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` exits `0`.
2. `grep -c "disabled={self || isPending}" components/UsersAdmin.tsx` prints `1`.
3. `git diff --name-only main..feat/admin-self-password-reset` prints exactly
   `telecaller-app/components/UsersAdmin.tsx`.
4. After Step 4: container `Up`, `/login` returns `200`.
