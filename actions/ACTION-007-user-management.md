# ACTION-007 — Admin user management: add user, reset password, deactivate

Owner: Anirban
Repo: anirban475/lead-manger
Working copy on VPS: `/root/projects/lead-manger`

## Why this exists

Today the only way to create a telecaller login is to SSH into the VPS and run
`node deploy/seed-user.mjs <email> "<name>" "<password>"`, then pipe the SQL into
psql. Nobody but Anirban can do it, and there is **no way at all** to reset a
forgotten password or to remove access when someone leaves — that account can
sign in forever. This adds a small admin screen inside the app for those three
jobs.

## The database is already prepared — do not touch it

Claude has already applied all DDL and grants on the live database:

- `app_users.is_active boolean NOT NULL DEFAULT true` exists.
- `telecaller_app` has SELECT / INSERT / UPDATE on `is_active`.
- `anirban@amatec.in` is now `role = 'admin'`. Everyone else is `'caller'`.

**This task is app code only. Do not run `psql`. Do not connect to the database.**
Record the schema in `deploy/schema.sql` for the record, but do not execute it.

## Four things that will silently break this task

**1. Deactivation does nothing unless login checks it.** `verifyCredentials` in
`telecaller-app/lib/auth.ts` selects a user by email and compares the bcrypt
hash. If it does not also require `is_active`, a deactivated user still signs in
and the whole feature is decorative. The login lookup **must reject inactive
users**, and must fail with the same generic "Invalid email or password" so it
does not leak which accounts exist.

**2. The session cookie carries a stale role.** `getSession()` reads `role` out
of the signed cookie that was minted at login time, so it does not reflect the
database. Someone demoted, or deactivated, keeps a valid admin cookie until it
expires. Therefore the admin gate must **not trust the cookie alone**: add a
helper in `lib/auth.ts`, e.g. `requireAdmin()`, that calls `getSession()` and
then **re-reads the user row from the database**, requiring `role = 'admin'` AND
`is_active = true`. Every one of the three server actions and the users page
must go through it.

**3. An admin can lock everybody out.** If the only admin deactivates or demotes
themselves, no one can ever manage users again. The actions must **refuse to let
a user deactivate their own account or change their own role**, and say so.

**4. The email column is UNIQUE (`app_users_email_key`).** Inserting a duplicate
throws Postgres error `23505` and would surface as a 500. Catch it and return a
friendly "That email already has an account." Normalise email with
`.trim().toLowerCase()` before insert and before lookup.

## Step 1 — report only, no changes

Read and report, changing nothing:

1. The full body of `verifyCredentials` and `getSession` in `telecaller-app/lib/auth.ts`.
2. The contents of `telecaller-app/app/(app)/layout.tsx` — specifically what it
   passes to `AppNav`.
3. The `NAV` array in `telecaller-app/components/AppNav.tsx`.
4. The bcrypt cost factor used in `telecaller-app/deploy/seed-user.mjs`.

Then state in one line how you will gate the admin page and actions.

Report key names only where credentials are involved. **Never print a password,
a hash, or any part of one.**

Stop after reporting. Do not write anything yet.

## Step 2 — build

Create or modify only these files:

**`telecaller-app/lib/auth.ts`** (modify)
- `verifyCredentials`: also require `is_active` on the looked-up user; return
  `null` for inactive accounts (same generic failure as a bad password).
- Add `export async function requireAdmin(): Promise<Session>` — calls
  `getSession()`, returns/throws per above: it must re-read `app_users` by email
  and require `role='admin' AND is_active`. Throw `new Error('Unauthorized')` if
  not.

**`telecaller-app/lib/users.ts`** (new)
- `export type AppUser = { id: number; email: string; display_name: string | null; role: string; is_active: boolean; created_at: string }`
- `export async function listUsers(): Promise<AppUser[]>` ordered by id.
- **Never select `password_hash`.** It must not leave the database layer.

**`telecaller-app/actions/createUser.ts`** (new, `'use server'`)
- `requireAdmin()` first.
- Inputs: email, display_name, password, role.
- Validate: email non-empty and contains `@`; display_name non-empty; password
  at least 8 characters; role must be exactly `'caller'` or `'admin'` (reject
  anything else — do not pass a free-form role through to SQL).
- Hash with `bcrypt.hashSync(password, 10)` (same cost as the existing users).
- INSERT into `app_users (email, password_hash, display_name, role, is_active)`
  with `is_active = true`. Catch `23505` → friendly duplicate-email message.
- `revalidatePath('/users')`. Return `{ success: boolean; error?: string }`.

**`telecaller-app/actions/resetUserPassword.ts`** (new, `'use server'`)
- `requireAdmin()` first. Inputs: user id, new password.
- Validate password ≥ 8 characters. Hash with cost 10.
- `UPDATE app_users SET password_hash = $1 WHERE id = $2`.
- `revalidatePath('/users')`. Never log or return the password or the hash.

**`telecaller-app/actions/setUserActive.ts`** (new, `'use server'`)
- `requireAdmin()` first. Inputs: user id, isActive boolean.
- **Refuse if the target user is the caller themselves** — compare against the
  session email — with the message "You cannot deactivate your own account."
- `UPDATE app_users SET is_active = $1 WHERE id = $2`. `revalidatePath('/users')`.

**`telecaller-app/app/(app)/users/page.tsx`** (new)
- Server component. Gate with `getSession()`; if there is no session or the user
  is not an admin (re-read from the database, same rule as `requireAdmin`),
  `redirect('/queue')` — do not render the page or leak that it exists.
- Otherwise fetch `listUsers()` and render `<UsersAdmin users={...} currentEmail={...} />`.

**`telecaller-app/components/UsersAdmin.tsx`** (new, `'use client'`)
- A `.table-responsive` + `.dense-table` list of users: Name, Email, Role,
  Status (Active / Inactive badge), Created.
- Per row: a **Reset password** button and a **Deactivate / Reactivate** button.
  Hide or disable both self-actions for the row matching `currentEmail`.
- An **+ Add User** button opening a modal with Name, Email, Password, Role
  (select: caller / admin).
- Reuse the existing modal pattern from `components/AddLeadForm.tsx`: backdrop
  `drawer-backdrop active`, a fixed centred `.card.pad` with
  `transform: translate(-50%,-50%)`, `maxHeight:'90vh'`, `overflowY:'auto'`.
  **Do not put `animate-fade-in` on the modal container** — its keyframes set
  `transform` and would break the centring (documented bug, already fixed once).
  Use `useTransition`, `.btn primary` / `.btn secondary`, `.input`, and
  `router.refresh()` on success.
- Password inputs must be `type="password"`.

**`telecaller-app/components/AppNav.tsx`** (modify)
- Accept an `isAdmin: boolean` prop; when true, append a `Users` nav entry
  (`/users`, icon `👥`) to both the sidebar and the mobile tab bar.
- The `who` block currently hardcodes the subtitle `telecaller`; show the actual
  role instead.

**`telecaller-app/app/(app)/layout.tsx`** (modify)
- Pass `isAdmin` down to `AppNav`, determined from the session role.

**`telecaller-app/deploy/schema.sql`** (modify, record only)
- Add, in the app_users section, without executing anything:
  ```sql
  ALTER TABLE app_users ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;
  GRANT SELECT (is_active), INSERT (is_active), UPDATE (is_active) ON app_users TO telecaller_app;
  -- Promote the owner account:  UPDATE app_users SET role='admin' WHERE email='anirban@amatec.in';
  ```

Non-goals: no forgot-password email flow, no password-strength meter, no user
delete, no changes to `lib/queries.ts` or any lead behaviour, no schema
execution, no deploy.

Then run these from `/root/projects/lead-manger/telecaller-app` and paste the
real output of each with its exit code. Not a summary.

```
node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```

**Use exactly that command.** Do **not** use `npx tsc` — in this clone it
resolves to an unrelated `tsc@2.0.4` package from the registry and proves
nothing. Run `npm ci` first if `node_modules` is missing.

```
grep -rn "requireAdmin" ../telecaller-app/actions ../telecaller-app/lib | head -20
```

```
grep -rn "password_hash" ../telecaller-app/lib/users.ts
```

The last grep must find **nothing** (exit 1) — the hash must never be selected
into the users list.

## Step 3 — commit

Only after Step 2 output is posted and looks right:

- Create a branch `feat/user-management` off `main`.
- Commit the changed and new files with a message describing the feature and the
  admin gate.
- Push with `git push -u origin feat/user-management`.
- Report the branch, the commit hash, and `git diff --name-only main..feat/user-management`.

Do **not** commit to `main`, do **not** merge, do **not** deploy.

## Rules for this task

- Work only inside `/root/projects/lead-manger`. Touch nothing else on the VPS.
- Do not touch `/opt/telecaller-app`. Do not run any `docker` command.
- **Do not connect to the database.** No `psql`. The DDL is already applied.
- Do not touch `.env` or any credential file. **Never print a password or a hash,
  not even partially, not even in a test.**
- Do not weaken the existing login: `verifyCredentials` must keep using
  `bcrypt.compare` and must keep returning the same generic failure.
- One step per reply. Finish a step, report, and wait.

## Acceptance

Done when, with pasted output:

1. `node node_modules/typescript/bin/tsc --noEmit -p tsconfig.json` exits `0`.
2. `grep -rn "requireAdmin" telecaller-app/actions telecaller-app/lib` shows it
   defined once in `lib/auth.ts` and called in **all three** action files.
3. `grep -rn "password_hash" telecaller-app/lib/users.ts` finds nothing, exit `1`.
4. `grep -n "is_active" telecaller-app/lib/auth.ts` shows the login lookup
   filtering on it.
5. The branch `feat/user-management` is pushed to `origin`.
