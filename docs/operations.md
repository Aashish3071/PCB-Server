# Operations & Diagnostics

Day-two runbook for the PCB Server: how to check that things are healthy,
where the background workers live, and what every knob does.

## 1. Quick health check

```bash
# Public — used by uptime checks / load balancers.
curl -s https://your-backend/api/v1/health | jq
```
Response shape:
```json
{
  "backend_status": "ok",
  "database_status": "ok",
  "last_telemetry_received": "2026-07-06T10:32:04Z",
  "api_version": "1.0",
  "frontend_version": "1.0"
}
```
- **`database_status: "error"`** → backend can't reach Postgres. Check
  `DATABASE_URL` and the Supabase project status.
- **`last_telemetry_received: null`** on a live fleet → devices are silent.
  Check the offline watchdog logs and rate limiter (below).

## 2. Deep diagnostics (admin only)

```bash
# Requires a Supabase JWT for an admin user.
TOKEN=$(supabase auth token)   # or grab one from the dashboard
curl -s -H "Authorization: Bearer $TOKEN" \
     https://your-backend/api/v1/diagnostics | jq
```
Sample:
```json
{
  "environment": "production",
  "fleet_by_status": {"ONLINE": 87, "OFFLINE": 3, "DISABLED": 1, "PROVISIONED": 2},
  "telemetry_rows": 4382110,
  "open_alerts": 4,
  "last_telemetry_received": "2026-07-06T10:32:04Z",
  "rate_limiter": {
    "tracked_devices": 90,
    "recent_hits": 4,
    "burst_limit": 5,
    "burst_window_seconds": 60,
    "floor_multiplier": 0.5
  },
  "config": {
    "device_offline_grace_multiplier": 3.0,
    "offline_watchdog_interval_seconds": 60,
    "telemetry_retention_days": 90,
    "alert_retention_days": 180,
    "retention_sweep_interval_seconds": 86400,
    "alert_low_battery_pct": 20.0,
    "alert_high_temp_c": 65.0,
    "alert_low_voltage_v": 11.5
  }
}
```
What to look for:
- **Sudden drop in `ONLINE`** → likely a cell-network outage or a bad OTA
  push. Cross-reference the timing with `open_alerts`.
- **`rate_limiter.recent_hits` growing fast** → a device is spamming; find
  it in the logs (`RATE_LIMIT_REJECTED`) and either fix its firmware loop or
  raise its `upload_interval_seconds`.
- **`telemetry_rows` climbing beyond your Supabase free-tier disk** → shorten
  `TELEMETRY_RETENTION_DAYS`; the retention worker will catch up on its next
  sweep.

## 3. Background workers

Both are started by the FastAPI lifespan handler
([`app/main.py`](../backend/app/main.py)) and stopped cleanly on shutdown. They
run **in-process** — no separate cron/celery is needed at 10-100 devices.

### 3a. Offline watchdog — [`app/workers/offline_watchdog.py`](../backend/app/workers/offline_watchdog.py)
- **What it does**: sweeps every `OFFLINE_WATCHDOG_INTERVAL_SECONDS`; any
  `ONLINE` device whose `last_seen_at` is older than
  `upload_interval_seconds × DEVICE_OFFLINE_GRACE_MULTIPLIER` is flipped to
  `OFFLINE` and gets a `DEVICE_OFFLINE` alert (deduped — one open alert per
  device).
- **Recovery**: when the device uploads again, the ingest path flips it back
  to `ONLINE` and auto-resolves the alert.
- **Log lines**: `Offline watchdog started`, `Device marked offline`,
  `Auto-resolved offline alerts on reconnect`.

### 3b. Retention worker — [`app/workers/retention.py`](../backend/app/workers/retention.py)
- **What it does**: once per `RETENTION_SWEEP_INTERVAL_SECONDS` deletes
  telemetry rows older than `TELEMETRY_RETENTION_DAYS` and resolved alerts
  older than `ALERT_RETENTION_DAYS`. Unresolved alerts are always kept.
- **Batching**: `RETENTION_BATCH_SIZE` rows per commit so a big backlog
  never opens a monster transaction (critical on Supabase free tier).
- **Set `TELEMETRY_RETENTION_DAYS=0`** to disable pruning entirely (useful
  during a compliance hold).
- **Log lines**: `Retention worker started`, `Retention sweep complete`.

## 4. Rate limiting — [`app/utils/rate_limit.py`](../backend/app/utils/rate_limit.py)

Applied to `POST /api/v1/telemetry` via the `check_rate_limit` dependency.
Two rules, both per-device, both in-memory:

1. **Floor**: no more than one upload per
   `upload_interval_seconds × floor_multiplier` (default 0.5). A device
   configured for 300s can't upload faster than every 150s.
2. **Burst**: at most `burst_limit` (default 5) uploads per
   `burst_window_seconds` (default 60).

On rejection the response is `429` with a `Retry-After` header (seconds).
Firmware [must respect it](firmware_integration.md#response-codes-and-what-firmware-should-do).

**Scaling caveat**: the state is per-process. If you ever run more than one
backend replica behind a load balancer, swap this for a Redis-backed
implementation — the `RateLimiter.check` signature is deliberately narrow so
that's a drop-in replacement.

## 5. Reading the logs

`ENVIRONMENT=production` switches structlog to JSON so a log collector can
parse it. Every telemetry-relevant action carries an `action=` field — grep on
that:

| `action=` | When it fires | What to check |
|-----------|---------------|---------------|
| `DEVICE_AUTH_FAILURE` | Bad UID, bad key, or disabled device tried to upload | Which `device_uid`? Was it recently rotated? |
| `TELEMETRY_INGESTED` | Successful upload | Baseline signal — should be steady |
| `TELEMETRY_DUPLICATE_IGNORED` | Same `(device_uid, timestamp)` re-uploaded | Usually harmless (network retry) |
| `RATE_LIMIT_REJECTED` | Device exceeded floor or burst | Check `retry_after_seconds`; is firmware runaway? |
| `DEVICE_ONLINE` | Device sent telemetry after being OFFLINE/PROVISIONED | Reconnect event — expected |
| `DEVICE_OFFLINE` | Watchdog flipped an ONLINE device to OFFLINE | Sanity-check `last_seen_at` and network conditions |
| `OFFLINE_ALERTS_RESOLVED` | Reconnect auto-cleared the alert | Paired with `DEVICE_ONLINE` |
| `ALERTS_GENERATED` | Threshold alert (low battery, high temp, low voltage) | Cross-reference telemetry payload |
| `RETENTION_SWEEP` | Retention worker deleted rows | Row counts logged |
| `PROVISION_DEVICE` | Admin added a new device | Audit trail |
| `RBAC_DENIED` | Non-admin tried an admin-only route | Suspicious — investigate |

Example filters (JSON logs):
```bash
# All authentication failures in the last hour
fly logs | jq 'select(.action=="DEVICE_AUTH_FAILURE")'
# Which devices are getting rate-limited?
fly logs | jq -r 'select(.action=="RATE_LIMIT_REJECTED") | .device_uid' | sort | uniq -c
```

## 6. Common diagnostic playbooks

### "Everything shows OFFLINE"
1. `curl /api/v1/health` — is `database_status: ok`?
2. `curl /api/v1/diagnostics` — is `last_telemetry_received` recent?
3. If it's stale by more than a few minutes: it's not the server, it's
   connectivity. Check the LTE-M/NB-IoT provider status.
4. If `last_telemetry_received` is recent but `fleet_by_status.ONLINE` is
   still 0: the watchdog is buggy — check logs for exceptions.

### "One specific device won't come online"
1. Grep logs for its `device_uid` — any `DEVICE_AUTH_FAILURE`?
2. In the dashboard, is its status `DISABLED`? Re-enable it.
3. If auth failures persist: **rotate the key** (dashboard →
   device → rotate) and re-flash.
4. If the device auths fine but nothing shows up: the request is being
   429'd — check `RATE_LIMIT_REJECTED` in logs and raise its
   `upload_interval_seconds`.

### "Alert storm"
1. `/api/v1/diagnostics` → `open_alerts` count.
2. `/api/v1/alerts?status=ACTIVE&page_size=100` → what alert_type?
3. If most are `DEVICE_OFFLINE` around the same timestamp: infrastructure
   event (cell outage). They'll auto-resolve when connectivity returns.
4. If most are `LOW_BATTERY` at night: seasonal — consider raising
   `ALERT_LOW_BATTERY_PCT` for the affected fleet.

### "Supabase is at 80% of the free-tier disk quota"
1. Diagnostics: what's `telemetry_rows`?
2. Cut `TELEMETRY_RETENTION_DAYS` (e.g., 90 → 30).
3. The retention worker sweeps within `RETENTION_SWEEP_INTERVAL_SECONDS`
   (default 24h). To sweep immediately, restart the backend — it runs on
   startup.
4. Longer-term: aggregate old telemetry into hourly summaries. Not
   implemented yet; see [decisions.md](decisions.md) if this becomes
   a priority.

## 7. All operational knobs (env vars)

Full descriptions in [`backend/.env.example`](../backend/.env.example). This is
just the map.

| Setting | Default | Effect |
|---------|---------|--------|
| `ENVIRONMENT` | `development` | `production` hides `/api/docs`, JSON logs |
| `DATABASE_URL` | Docker local | asyncpg URI; Supabase in prod |
| `CORS_ORIGINS` | localhost | Comma-separated allowed origins |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | — | Auth/JWKS |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | — | Bootstrap only |
| `ALERT_LOW_BATTERY_PCT` | 20.0 | Below → `LOW_BATTERY` |
| `ALERT_HIGH_TEMP_C` | 65.0 | Above → `HIGH_TEMPERATURE` |
| `ALERT_LOW_VOLTAGE_V` | 11.5 | Below → `LOW_VOLTAGE` |
| `DEVICE_OFFLINE_GRACE_MULTIPLIER` | 3.0 | Missed uploads before OFFLINE |
| `OFFLINE_WATCHDOG_INTERVAL_SECONDS` | 60 | Watchdog sweep cadence |
| `TELEMETRY_RETENTION_DAYS` | 90 | 0 disables pruning |
| `ALERT_RETENTION_DAYS` | 180 | Only resolved alerts are pruned |
| `RETENTION_SWEEP_INTERVAL_SECONDS` | 86400 | Retention sweep cadence |
| `RETENTION_BATCH_SIZE` | 10000 | Rows per delete batch |
