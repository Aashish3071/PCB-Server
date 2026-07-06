# Deployment Guide

Production deployment of the IoT Device Management Server for real hardware and
real users. Target scale: 10–100 devices on free/low-cost tiers.

## Architecture at a glance

| Component | What | Recommended host (free/cheap) |
|-----------|------|-------------------------------|
| Database + Auth | Supabase (Postgres + Auth/JWKS) | Supabase free tier |
| Backend API | FastAPI (this repo, `backend/`) | Fly.io / Render / Railway |
| Frontend SPA | React + Vite static build (`frontend/`) | Vercel / Netlify / Cloudflare Pages |

Devices authenticate to the backend with `X-Device-UID` + `X-API-Key`. Humans
authenticate to Supabase, and the backend validates the Supabase JWT via JWKS.

---

## 1. Database + Auth: Supabase

> The step-by-step database cutover (with a rollback plan) is in
> **[docs/supabase_migration.md](docs/supabase_migration.md)**. Do that once,
> then use this document for the host-side steps.

1. Create a Supabase project. Enable **Email/Password** auth (Authentication → Providers).
2. Get the connection string: **Project Settings → Database → Connection string → URI**.
   Use the **Session pooler (port 5432)** — this app uses nested transactions
   (`SAVEPOINT`s) for idempotent telemetry, which require session mode.
   Convert it to the asyncpg driver:
   ```
   DATABASE_URL=postgresql+asyncpg://postgres.<project-ref>:<db-password>@<pooler-host>:5432/postgres
   ```
3. Note these from **Project Settings → API**:
   - `SUPABASE_URL` (Project URL)
   - `SUPABASE_SERVICE_ROLE_KEY` — **secret, backend only**
   - anon / publishable key — public, used by the frontend

---

## 2. Backend (FastAPI)

Env vars (see [backend/.env.example](backend/.env.example)):

| Var | Value |
|-----|-------|
| `ENVIRONMENT` | `production` (disables `/api/docs`, JSON logs) |
| `DATABASE_URL` | Supabase asyncpg URI from step 1 |
| `CORS_ORIGINS` | your frontend origin, e.g. `https://your-app.vercel.app` |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | secret service-role key |
| `SUPABASE_JWT_AUDIENCE` | `authenticated` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | for one-time admin bootstrap |

A production `Dockerfile` is included. It installs from `uv.lock`, runs
`alembic upgrade head` on start, then serves uvicorn on `$PORT` (defaults 8000).

### Deploy to Fly.io (example)
```bash
cd backend
fly launch --no-deploy                 # generates fly.toml; keep internal_port 8000
fly secrets set \
  DATABASE_URL='postgresql+asyncpg://...' \
  SUPABASE_URL='https://<ref>.supabase.co' \
  SUPABASE_SERVICE_ROLE_KEY='...' \
  CORS_ORIGINS='https://your-app.vercel.app' \
  ENVIRONMENT='production'
fly deploy
```
Render/Railway: point at `backend/`, they auto-detect the Dockerfile; set the
same env vars in the dashboard. Prefer an always-on instance (device telemetry
is continuous — free tiers that sleep on idle will drop uploads).

### Run migrations
The container runs `alembic upgrade head` automatically on boot. To run manually:
```bash
cd backend && DATABASE_URL='...' uv run alembic upgrade head
```

### Bootstrap the first admin (run once)
```bash
cd backend
ADMIN_EMAIL='you@example.com' ADMIN_PASSWORD='a-strong-password' \
  DATABASE_URL='<supabase-uri>' SUPABASE_URL='...' SUPABASE_SERVICE_ROLE_KEY='...' \
  PYTHONPATH=. uv run python scripts/create_admin.py
```
The script refuses to run with a blank password. It creates the user in Supabase
Auth and mirrors it into the local `users` table with `role=admin`.

---

## 3. Frontend (React + Vite)

`VITE_*` values are **baked in at build time** (see
[frontend/.env.local.example](frontend/.env.local.example)) and shipped in the
browser bundle — use public values only (never the service-role key):

| Var | Value |
|-----|-------|
| `VITE_API_URL` | backend base URL, e.g. `https://your-backend.fly.dev` |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | anon / publishable key |

### Deploy to Vercel/Netlify
- Framework preset: **Vite**, build command `npm run build`, output `dist/`.
- Set the three `VITE_*` env vars in the host dashboard.
- SPA routing: Vercel/Netlify handle it automatically. For custom nginx hosting,
  the included [frontend/nginx.conf](frontend/nginx.conf) does the `try_files`
  fallback to `index.html`.

After the frontend is live, add its origin to the backend's `CORS_ORIGINS` and redeploy.

---

## 4. Full stack via Docker (self-hosting alternative)

Runs Postgres + backend + nginx-served frontend together.
```bash
cp .env.example .env                 # set POSTGRES_*, VITE_*, CORS_ORIGINS
cp backend/.env.example backend/.env # set SUPABASE_* values
docker compose up --build
# backend  -> http://localhost:8000
# frontend -> http://localhost:8080
# then bootstrap admin (section 2)
```

---

## 5. Simulator (testing only — not production)

`simulator/` is a load-testing tool, not part of the deployment. Point it at a
**staging** backend to generate telemetry; do not run it against production data.

---

## Go-live checklist

- [ ] `ENVIRONMENT=production` on the backend (docs disabled, JSON logs)
- [ ] `CORS_ORIGINS` set to the real frontend origin(s) only
- [ ] `SUPABASE_SERVICE_ROLE_KEY` set on the backend only; frontend uses the anon key
- [ ] Strong `ADMIN_PASSWORD`; admin bootstrapped once, then unset the env var
- [ ] `alembic upgrade head` applied to the Supabase database
- [ ] Database is empty of mock/test data (customers, devices, telemetry, alerts)
- [ ] Rotate any keys that were shared during development
- [ ] Rate limiting active on the telemetry endpoint (default: floor + 5/min burst per device — see [docs/operations.md](docs/operations.md#4-rate-limiting--apputilsrate_limitpy))
- [ ] Telemetry retention set (default 90 days; `TELEMETRY_RETENTION_DAYS`)
- [ ] `/api/v1/diagnostics` reachable as admin — bookmark it for day-two ops
