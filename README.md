# IoT Device Management Server (DMS)

A robust, production-ready IoT Device Management Server designed for Solar Street Light RMS controllers. 

## Features
- **Supabase Authentication**: Secure JWT-based authentication using PyJWKClient and asymmetric validation.
- **Role-Based Access Control**: Admins and Customers with strict data isolation.
- **Device Management**: Provisioning, disabling, and API-key-based hardware authentication.
- **Telemetry Ingestion**: High-frequency payload validation and time-series data storage.
- **Real-time Alerts**: Automated active/resolved alert state tracking based on telemetry thresholds.
- **Hardware Simulator**: Included Python simulator for load testing and golden-path verification.

## Tech Stack
- **Frontend**: React, Vite, Tailwind CSS, Zustand, React Router
- **Backend**: FastAPI (Python), Uvicorn, Pydantic
- **Database**: PostgreSQL (Supabase-hosted), SQLAlchemy (Async), Alembic
- **Authentication**: Supabase (Auth + JWKS)

## Prerequisites
- Node.js 18+
- Python 3.11+ (with `uv` package manager)
- Docker Desktop
- A Supabase Project (with Email/Password auth enabled)

## Local Development Setup

### 1. Database
```bash
docker run --name iot-postgres -e POSTGRES_USER=iotadmin -e POSTGRES_PASSWORD=secretpassword -e POSTGRES_DB=iot_dms -p 5432:5432 -d postgres:15
```

### 2. Backend Setup
Create `backend/.env` with your Supabase credentials:
```env
DATABASE_URL=postgresql+asyncpg://iotadmin:secretpassword@localhost:5432/iot_dms
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>
SUPABASE_JWT_AUDIENCE=authenticated
```

Install dependencies, run migrations, and create the admin user:
```bash
cd backend
uv sync
uv run alembic upgrade head
# Admin creds come from the environment (the script refuses a blank password):
ADMIN_EMAIL='you@example.com' ADMIN_PASSWORD='a-strong-password' \
  PYTHONPATH=. uv run python scripts/create_admin.py
```
Start the backend: `uv run uvicorn app.main:app --reload`

> For production (Supabase-hosted DB, free-tier hosting, Docker), see **[DEPLOYMENT.md](DEPLOYMENT.md)**.

### 3. Frontend Setup
Create `frontend/.env.local`:
```env
VITE_SUPABASE_URL=https://<your-project>.supabase.co
VITE_SUPABASE_ANON_KEY=<your-anon-key>
VITE_API_URL=http://localhost:8000
```
Install dependencies and run:
```bash
cd frontend
npm install
npm run dev
```

### 4. Running the Simulator
To test data ingestion, run the hardware simulator:
```bash
cd simulator
uv run python main.py
```
The simulator honors the server-side `upload_interval_seconds` on each virtual
device (via the `next_upload_seconds` control channel), so it's also a working
reference for how firmware should behave.

## Documentation

| Doc | Read when |
|-----|-----------|
| [docs/hardware_connection_guide.md](docs/hardware_connection_guide.md) | You want the end-to-end steps to connect a PCB/hardware device to the server (provision → credentials → first telemetry → Online) |
| [docs/operator_guide.md](docs/operator_guide.md) | You're operating the dashboard (add customer, provision device, tune upload interval, resolve alerts) |
| [docs/firmware_integration.md](docs/firmware_integration.md) | You're writing firmware for a PCB device — full contract + ESP32/MicroPython reference + smoke-test checklist |
| [docs/operations.md](docs/operations.md) | You're on-call — `/health` + `/diagnostics`, log filters, incident playbooks, every knob |
| [docs/api.md](docs/api.md) | REST endpoint reference |
| [docs/supabase_migration.md](docs/supabase_migration.md) | You're moving the DB from local Docker to Supabase Postgres |
| [DEPLOYMENT.md](DEPLOYMENT.md) | You're deploying to Fly/Vercel/Docker |
