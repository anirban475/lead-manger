# Telecaller Cockpit — deploy runbook

Next.js (App Router) app on top of the isolated `leads` Postgres. Runs as a
container on the `shared-network` Docker network and reaches `shared-postgres`
by hostname. Host nginx terminates TLS at `calls.amatec.in`.

## 0. Database (once)

Apply `deploy/schema.sql` as the `leads` owner / `admin` superuser:

```
docker exec -i shared-postgres psql -U admin -d leads < deploy/schema.sql
```

This creates `telecall_logs`, `app_users`, the `leads` denorm columns, the
`query_conversion` view, and the least-privilege `telecaller_app` role. The role
password is set separately (see below) and written into `.env`.

Seed users (per person):

```
node deploy/seed-user.mjs bhratti@amatec.in "Bhratti" "<temp-password>" \
  | docker exec -i shared-postgres psql -U admin -d leads
```

`seed-user.mjs` always writes `role = 'caller'`. For an `admin` or `manager`,
run a follow-up `UPDATE app_users SET role = '<role>' WHERE email = '<email>'`.

## 1. Build & run the container

On the VPS at `/opt/telecaller-app/` with a `.env` (see `.env.example`):

```
docker compose up -d --build
docker network inspect shared-network | grep telecaller-app   # confirm it joined
```

The app listens on `127.0.0.1:3020`.

## 2. TLS + nginx

1. Point DNS: `calls.amatec.in` A record → VPS IP.
2. `cp deploy/nginx-calls.amatec.in.conf /etc/nginx/sites-available/calls.amatec.in`
3. `certbot --nginx -d calls.amatec.in` (issues the cert and wires ssl_certificate lines)
4. `ln -s /etc/nginx/sites-available/calls.amatec.in /etc/nginx/sites-enabled/`
5. `nginx -t && systemctl reload nginx`

## 3. Redeploy after code changes

```
git pull   # or rsync the app dir
docker compose up -d --build
```

## Deploy traps

**`/opt/telecaller-app` is not a git checkout.** It is a plain copy holding the
`.env`, and it is what actually gets built. The git working copy lives at
`/root/projects/lead-manger/telecaller-app`. Committing and pushing changes
nothing on the running site. You must copy the changed files across first:

```
SRC=/root/projects/lead-manger/telecaller-app
DST=/opt/telecaller-app
cp "$SRC/lib/foo.ts" "$DST/lib/foo.ts"      # per changed file, or rsync
cd "$DST" && docker compose up -d --build
```

Never `rsync --delete` into `/opt/telecaller-app`. It would take the `.env` with
it and the container will not start. That directory also carries a pile of
`*.bak.actionNNN` files from earlier runs which do not exist in the repo, so a
mirroring sync in either direction will surprise you.

**The app connects as `telecaller_app`, not `leads_user`.** Any grant written
for a new database or view must name `telecaller_app` or the page 500s with
permission denied. `leads_user` owns the `leads` database but is not what the
app authenticates as.

**`npm run build` must pass with no environment set.** Next.js imports every
page module during page data collection, so anything that throws at module load
kills the build. `lib/db.ts` and `lib/coachingDb.ts` both resolve their
connection lazily for this reason. If you add a third pool, do the same, and
test with `env -u DATABASE_URL -u COACHING_DATABASE_URL npm run build`.

**Login is a server action, not a form POST.** A plain `curl -X POST /login`
returns 200 and sets no cookie. To smoke test an authenticated page, mint a
`tc_session` cookie directly: it is
`base64url(JSON{email,displayName,role,exp})` followed by `.` and the
base64url HMAC-SHA256 of that body keyed on `AUTH_SECRET`.

## Known broken, not yet fixed

`GET /stats` throws `permission denied for view query_conversion`. The
`query_conversion` view grants `SELECT` to `admin` and `n8n_leads` only, never
to `telecaller_app`, so the page has been failing for anyone using the app. One
grant fixes it:

```
GRANT SELECT ON query_conversion TO telecaller_app;
```

Left unapplied deliberately, it was found during unrelated work and is Anirban's
call.

## Notes

- The app connects ONLY as `telecaller_app` (SELECT/UPDATE leads, INSERT
  telecall_logs/suppression, SELECT query_conversion, R/W app_users). No DELETE,
  no access to radar_runs. Isolation preserved.
- `/performance` additionally reads the `telecaller_coaching` database through a
  second pool. See the "Call quality lives in a second database" section of
  `telecaller-app/README.md`.
- The new `leads` columns (`last_disposition`, `last_called_at`, `call_count`)
  sit outside the scraper's `save_leads` upsert list, so re-scrapes never touch
  them. Do not add them to that list without revisiting.
- Free host port chosen: 3020 (5678/5679/5001/5010/5432/5433/5440/4174/4180
  were taken — verify with `ss -ltnp` before deploy).
