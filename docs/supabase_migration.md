# Supabase Postgres Migration Runbook

**Current state (2026-07-06): migration complete.** `backend/.env`'s
`DATABASE_URL` now points at Supabase Postgres via the session pooler (port
5432). Alembic schema applied (head: `c9e1f2a4d6b8`), admin bootstrapped,
`/api/v1/health` confirms `database_status: ok`. The Docker Postgres instance
is no longer used by the backend — this document is kept as the reference for
how it was done and for future environments (staging, a second admin's laptop,
etc). The exact connection string lives only in `backend/.env` (gitignored) —
never commit it.

**Note on the direct connection host:** `db.<ref>.supabase.co` resolves to
**IPv6 only** (no A record) — it failed with `No route to host` on a
IPv6-less network. Use the session pooler instead (below), which serves IPv4.
Also note: the pooler region/prefix is **not derivable from the project ref** —
you must copy it from Project Settings → Database → Connection string → Session
pooler tab. Don't assume `aws-0-<region>`; newer projects land on other pooler
node prefixes (e.g. `aws-1-…`), so use whatever the dashboard shows.

## Why session-mode pooler (this bit us before)

Supabase gives you two pooler ports:
- **6543** — transaction mode. Fast, but **breaks `SAVEPOINT`** (nested transactions).
- **5432** — session mode. This is what we need — telemetry ingest uses
  `db.begin_nested()` for idempotency.

**Always use port 5432**, always drive it through `asyncpg`.

## The runbook

### Step 1 — provision the Supabase project (if not done)
1. https://supabase.com → new project (free tier is fine for 10-100 devices).
2. Wait for the DB to provision (~2 min).
3. Project Settings → Database → Connection string → **URI** → copy the
   session-pooler variant. It looks like:
   ```
   postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```
4. Rewrite it for asyncpg:
   ```
   postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
   ```

### Step 2 — apply the schema
Alembic owns the schema; there's no manual DDL step.
```bash
cd backend
DATABASE_URL='postgresql+asyncpg://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
  uv run alembic upgrade head
```
This creates every table (customers, users, devices, telemetry, alerts) and
the `device_uid_seq` sequence. If it fails, the URL is wrong or the network is
blocked — nothing is left half-applied because Alembic runs each migration
inside a transaction.

### Step 3 — decide: fresh start or copy local data?

**Fresh start (recommended for the very first cutover)**
- Do nothing after step 2. The DB is empty, ready for the first admin bootstrap.
- Skip to step 5.

**Copy the local dev DB** (only if you have real work to preserve)
- The current local DB should be treated as **dev data** — devices, customers,
  and telemetry there are test artifacts from the build. In almost every case
  you want a fresh Supabase, not a copy. If you have specific rows worth
  keeping, run:
```bash
# Dump only the tables that have real user data (customers/devices), skip telemetry.
docker exec iot-postgres pg_dump -U iotadmin -d iot_dms \
  --data-only --no-owner \
  --table=customers --table=devices --table=users \
  > /tmp/pcb_seed.sql

# Load into Supabase.
psql 'postgresql://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
     < /tmp/pcb_seed.sql
```
**Caveat**: the `users` table has a Supabase Auth foreign key on `id`. If you
copy user rows, the corresponding auth.users must also exist in the new
Supabase project — which they won't. Almost always: **don't copy users, just
re-bootstrap the admin.**

### Step 4 — flip the backend config
Edit `backend/.env` (never commit it):
```bash
DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<pw>@aws-0-<region>.pooler.supabase.com:5432/postgres
ENVIRONMENT=production          # if you're also cutting over to prod
CORS_ORIGINS=https://your-frontend.vercel.app
```
Keep the Supabase Auth vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`) —
they already point at the right project.

### Step 5 — bootstrap the admin
```bash
cd backend
ADMIN_EMAIL='you@example.com' ADMIN_PASSWORD='<strong-generated-password>' \
  PYTHONPATH=. uv run python scripts/create_admin.py
```
Creates the Supabase Auth user and the local `users` row with `role=admin`.
Then **unset `ADMIN_PASSWORD`** — it should not sit in your shell history or
production env.

### Step 6 — smoke test
```bash
# Backend running against Supabase now:
uv run uvicorn app.main:app

# In another shell:
curl -s http://localhost:8000/api/v1/health | jq
# Expect: database_status: "ok"

# Log in through the dashboard, provision one device, POST one telemetry
# reading with its X-Device-UID + X-API-Key. Check /api/v1/diagnostics as the
# admin — telemetry_rows should be 1.
```

### Step 7 — production hosting
Now that the data path works against Supabase, deploy the backend where you
want it (Fly/Render/Railway) with the same `DATABASE_URL`. See
[deployment.md](deployment.md) for the host-side steps.

## Rollback plan (if the cutover fails)
Because the app is env-driven, rollback is one variable:
```bash
# In backend/.env — point back at the local Docker DB.
DATABASE_URL=postgresql+asyncpg://iotadmin:secretpassword@localhost:5432/iot_dms
```
Restart the backend. The Supabase DB is left untouched for a second attempt.

## What to verify AFTER the migration
- `curl /api/v1/health` → `database_status: ok`
- `curl /api/v1/diagnostics` (as admin) → matches expected `fleet_by_status`
- Log lines `Application startup`, `Offline watchdog started`, `Retention
  worker started` all present
- One end-to-end telemetry upload from a real device — the Dashboard shows
  it inside 60s
