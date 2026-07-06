# Architecture Overview

This document outlines the high-level architecture of the IoT Device Management Server (DMS).

## 1. System Components

The system is composed of four primary components:
1. **Frontend SPA** (React/Vite)
2. **Backend API** (FastAPI)
3. **Database** (PostgreSQL)
4. **Hardware Simulator** (Python)

---

## 2. Authentication & Authorization

We use a modern, decoupled authentication architecture leveraging **Supabase**:

### User Authentication (Frontend)
1. The **Frontend** authenticates users directly with Supabase via the `VITE_SUPABASE_ANON_KEY`.
2. Supabase returns a JWT access token containing the user's UUID.
3. The Frontend attaches this JWT as a `Bearer` token to all backend API requests.
4. The **Backend** retrieves Supabase's public JWKS keys from `/.well-known/jwks.json` using `PyJWKClient`.
5. The JWT signature, issuer, expiration, and audience are strictly validated asynchronously.
6. The Backend maps the token's `sub` (UUID) to the local PostgreSQL `users` table to determine role-based access.

### Hardware Authentication (Simulator / Real Devices)
1. IoT Devices do not use JWTs. They use long-lived, securely hashed API keys.
2. Hardware sends requests with `X-Device-UID` and `X-API-Key` headers.
3. The Backend hashes the incoming API key and compares it to the stored `api_key_hash`.

---

## 3. Database Schema Design

The relational database is designed around core domain entities:

- **Users**: Local representation of Supabase users. Contains roles (`admin`, `customer`) and permissions.
- **Customers**: Organizations or owners that devices are assigned to.
- **Devices**: Physical hardware entities. Contains firmware versions, connection status, and API key hashes.
- **Telemetry**: High-volume, time-series data reported by devices (e.g., voltage, temperature).
- **Alerts**: Stateful anomaly tracking. Alerts transition between `ACTIVE` and `RESOLVED`.

Migrations are managed strictly via **Alembic** to ensure reproducible schema deployments.

---

## 4. API Design

The Backend uses a modular **FastAPI** structure:
- `/api/v1/health`: Basic system liveness checks.
- `/api/v1/auth`: Local session validations.
- `/api/v1/users`: User profile and permission retrieval (`/me`).
- `/api/v1/customers`: CRUD operations for customers.
- `/api/v1/devices`: Provisioning, key rotation, and metadata updates.
- `/api/v1/telemetry`: High-throughput ingestion endpoint for hardware devices.
- `/api/v1/alerts`: Aggregated endpoints for monitoring system anomalies.

All endpoints enforce Pydantic schema validation to prevent invalid data or SQL injection attacks.

---

## 5. Security & Isolation

- **CORS**: Strictly limited to approved frontend origins.
- **Secret Management**: The `Service Role Key` is isolated exclusively to the backend. The frontend only contains the safe `Anon Key`.
- **Data Isolation**: Customers can only access devices and telemetry associated with their explicit `customer_id`.
- **Fail-Fast Configuration**: The backend validates the presence of all required environment variables on startup.
