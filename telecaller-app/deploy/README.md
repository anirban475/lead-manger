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

## Notes

- The app connects ONLY as `telecaller_app` (SELECT/UPDATE leads, INSERT
  telecall_logs/suppression, SELECT query_conversion, R/W app_users). No DELETE,
  no access to radar_runs. Isolation preserved.
- The new `leads` columns (`last_disposition`, `last_called_at`, `call_count`)
  sit outside the scraper's `save_leads` upsert list, so re-scrapes never touch
  them. Do not add them to that list without revisiting.
- Free host port chosen: 3020 (5678/5679/5001/5010/5432/5433/5440/4174/4180
  were taken — verify with `ss -ltnp` before deploy).
