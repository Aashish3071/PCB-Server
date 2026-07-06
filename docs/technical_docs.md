# PCB Server - Technical Documentation

## 1. Architecture Overview
The PCB Server is a modern web application built for managing Solar Street Light RMS devices.
- **Frontend**: React, TypeScript, Tailwind CSS, Vite
- **Backend**: FastAPI, Python, SQLAlchemy, asyncpg
- **Database**: PostgreSQL
- **Authentication**: Supabase Auth

## 2. Installation & Configuration

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- `uv` Python package manager

### Environment Variables
#### Backend (`backend/.env`)
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/iot_dms
SUPABASE_URL=https://your-project.supabase.co
```
*(If Supabase URL is omitted, the backend falls back to unverified local JWT decoding for development only).*

#### Frontend (`frontend/.env.local`)
```env
VITE_API_URL=http://localhost:8000
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

## 3. Deployment
### Backend
1. Apply database migrations:
   ```bash
   uv run alembic upgrade head
   ```
2. Start the production server (e.g., using Gunicorn/Uvicorn):
   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

### Frontend
1. Build the production artifacts:
   ```bash
   npm run build
   ```
2. Serve the `dist` folder via Nginx or a static hosting provider (e.g., Vercel, Netlify).

## 4. Simulator Usage
A built-in simulator is provided for load testing and development.
1. Navigate to the `simulator` directory.
2. Configure the behavior in `config/default.yaml`.
3. Ensure devices are seeded in the database:
   ```bash
   cd ../backend
   PYTHONPATH=. uv run python scripts/seed_devices.py
   ```
4. Run the simulator:
   ```bash
   cd ../simulator
   uv run python main.py
   ```

## 5. API Reference
- **Swagger UI**: Available at `http://localhost:8000/docs` when the backend is running.
- **Core Endpoints**:
  - `POST /api/v1/telemetry`: Ingest telemetry (Requires `X-Device-UID` and `X-API-Key` headers).
  - `GET /api/v1/devices/{id}/overview`: Get aggregated analytics for the Device Details view.
  - `GET /api/v1/health`: System health status.

## 6. Firmware Integration
Firmware developers must ensure their devices implement the following requirements:
- Send `POST` requests to the telemetry endpoint.
- Include the `X-Device-UID` and `X-API-Key` headers.
- Transmit a JSON payload matching the `TelemetryIngest` schema.
- Implement an offline buffering mechanism to store readings if the network is unavailable, and replay them sequentially upon reconnection.
