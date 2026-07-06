# Firmware Integration Guide (Device-Side)

This is the contract every PCB device must follow to talk to the PCB Server. If
you're writing firmware for the Solar Street Light RMS controller (or any
device meant to report to this server), this is the reference.

The server side of this contract is stable — schema at
[api.md](api.md) and [`backend/app/api/v1/telemetry.py`](../backend/app/api/v1/telemetry.py).

## 1. What you get during provisioning

An admin provisions your device in the dashboard and hands you two strings —
this is the **only** time the plaintext API key ever exists:

| Field | Example | Where it goes |
|-------|---------|---------------|
| `device_uid` | `SLRMS-000042` | Flashed into firmware (or NVS/EEPROM) |
| `api_key_plaintext` | `2fb3b3…` (32-char secret) | Flashed into firmware **as a secret** |

If either is lost, the admin rotates the key (POST `/api/v1/devices/{id}/rotate-key`) —
never try to "recover" it.

## 2. The telemetry loop (the whole contract)

```
   ┌────────────────────────────────────────────┐
   │  Wake up                                   │
   │  Read sensors → build JSON payload         │
   │  POST /api/v1/telemetry (headers + body)   │
   │  Read next_upload_seconds from response    │
   │  Deep-sleep for next_upload_seconds        │
   └────────────────────────────────────────────┘
```

That's it. Two headers, one JSON body, one response field to obey. Because
`next_upload_seconds` comes from the server, the admin can retune your device's
cadence from the dashboard — no reflash needed.

### Request

```http
POST /api/v1/telemetry HTTP/1.1
Host: your-backend.example.com
X-Device-UID: SLRMS-000042
X-API-Key: <plaintext key from provisioning>
Content-Type: application/json

{
  "timestamp": "2026-07-06T10:30:00Z",   // REQUIRED, ISO-8601 UTC
  "panel_voltage": 18.4,                  // all sensor fields OPTIONAL
  "battery_voltage": 12.6,
  "battery_percentage": 78.5,
  "charging_current": 2.1,
  "charging_status": true,
  "light_load_status": false,
  "temperature": 38.2,
  "humidity": 55.0,
  "signal_strength": 65,
  "firmware_version": "1.0.3",
  "network_type": "LTE-M",
  "boot_count": 217,
  "uptime_seconds": 84432,
  "hardware_version": "rev-B"
}
```

Any field the device doesn't have: just omit it. Full field list and ranges in
[api.md](api.md) and [`schemas/telemetry.py`](../backend/app/schemas/telemetry.py).

### Response — this is the control channel

```json
{
  "status": "accepted",
  "server_time": "2026-07-06T10:30:01.234Z",
  "next_upload_seconds": 300
}
```

- **`next_upload_seconds`** — the number of seconds the device should sleep
  before its next upload. **The firmware MUST honor this** — it's how the
  admin retunes the fleet.
- **`server_time`** — useful for clock drift correction if the device has an
  RTC but no NTP.

### Response codes and what firmware should do

| Code | Meaning | Firmware action |
|------|---------|-----------------|
| `200` | Accepted (also for duplicate timestamps — idempotent) | Clear the payload from local buffer, sleep `next_upload_seconds` |
| `401` | Unknown UID or wrong API key | **Do not retry.** Store the payload; the device is misconfigured or de-provisioned. Blink an error LED / log for a technician |
| `403` | Device is `DISABLED` in the dashboard | Same as 401 — do not spam retries. Back off aggressively (hours) |
| `422` | Payload failed validation (e.g., temp out of range) | Log locally, drop the payload, do not retry the same one |
| `429` | Rate limit hit | **Read `Retry-After` header** (seconds), sleep that long, then retry |
| `5xx` / network error | Server transient | Exponential backoff (30s → 60s → 120s → …), keep the payload in local buffer, retry — **do not drop data** |

### Time discipline

- All timestamps MUST be UTC ISO-8601 with the trailing `Z` (or `+00:00`).
- Duplicate `(device_uid, timestamp)` is silently deduped by the server, so
  retrying an in-flight upload is safe.
- If the device has no reliable clock (no RTC, no NTP), it may fall back to
  server time drawn from the previous response's `server_time`.

## 3. Reference implementations

### 3a. ESP32 / Arduino (C++, HTTPS)

Minimum viable loop — no local buffering, no retries. Wire in
`ArduinoJson`, `WiFiClientSecure`, `HTTPClient`. Add your own retry queue for
production.

```cpp
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

const char* SERVER = "https://your-backend.example.com";
const char* DEVICE_UID = "SLRMS-000042";
const char* API_KEY   = "REPLACE_WITH_PROVISIONED_KEY";

uint32_t nextUploadSeconds = 300;  // default until server tells us otherwise

bool sendTelemetry() {
  HTTPClient http;
  http.begin(String(SERVER) + "/api/v1/telemetry");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-UID", DEVICE_UID);
  http.addHeader("X-API-Key",    API_KEY);

  StaticJsonDocument<512> body;
  body["timestamp"]          = isoTimestampUtc();       // your RTC helper
  body["panel_voltage"]      = readPanelVoltage();
  body["battery_voltage"]    = readBatteryVoltage();
  body["battery_percentage"] = readBatteryPercent();
  body["temperature"]        = readTempC();
  body["firmware_version"]   = "1.0.3";

  String out;
  serializeJson(body, out);
  int code = http.POST(out);

  if (code == 200) {
    StaticJsonDocument<256> resp;
    if (!deserializeJson(resp, http.getString())) {
      if (resp.containsKey("next_upload_seconds")) {
        nextUploadSeconds = resp["next_upload_seconds"].as<uint32_t>();
      }
    }
    http.end();
    return true;
  }

  if (code == 429) {
    int retryAfter = http.header("Retry-After").toInt();
    if (retryAfter > 0) nextUploadSeconds = retryAfter;
  }
  http.end();
  return false;
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) sendTelemetry();
  esp_sleep_enable_timer_wakeup(uint64_t(nextUploadSeconds) * 1000000ULL);
  esp_deep_sleep_start();
}
```

### 3b. MicroPython (any ESP/RP2040 with `urequests`)

```python
import ujson, urequests, utime, machine

SERVER      = "https://your-backend.example.com"
DEVICE_UID  = "SLRMS-000042"
API_KEY     = "REPLACE_WITH_PROVISIONED_KEY"

next_upload = 300

def send_telemetry():
    global next_upload
    payload = {
        "timestamp":          iso_utc_now(),           # your RTC helper
        "panel_voltage":      read_panel_voltage(),
        "battery_voltage":    read_battery_voltage(),
        "battery_percentage": read_battery_percent(),
        "temperature":        read_temp_c(),
        "firmware_version":   "1.0.3",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Device-UID": DEVICE_UID,
        "X-API-Key":    API_KEY,
    }
    try:
        r = urequests.post(SERVER + "/api/v1/telemetry",
                           data=ujson.dumps(payload), headers=headers)
        if r.status_code == 200:
            next_upload = r.json().get("next_upload_seconds", next_upload)
        elif r.status_code == 429:
            next_upload = int(r.headers.get("Retry-After", next_upload))
        r.close()
    except Exception:
        pass  # keep next_upload as-is, try again next cycle

while True:
    send_telemetry()
    machine.deepsleep(next_upload * 1000)
```

### 3c. Python reference (already in this repo)

The [`simulator/`](../simulator/) is the canonical working reference: it
authenticates, sends valid payloads, and honors `next_upload_seconds` — see
[`simulator/devices/fleet.py`](../simulator/devices/fleet.py) `_device_loop()`
and [`simulator/telemetry_client.py`](../simulator/telemetry_client.py).

## 4. Firmware "smoke test" checklist

Before shipping a batch of devices, verify each one on the bench:

1. Flash firmware with `DEVICE_UID` + `API_KEY` from provisioning.
2. Power on with the backend URL pointing at **staging** (never provision real
   devices against production first).
3. Watch the backend logs for a `DEVICE_ONLINE` transition (see
   [operations.md](operations.md#reading-the-logs)).
4. In the dashboard: device appears **Online** and battery/voltage populate.
5. Edit the device, change **Upload Interval** to 60s, save.
6. On the next upload the response should carry `"next_upload_seconds": 60`
   and the device should now upload once a minute — proves the control loop.
7. Disable the device in the dashboard → next upload gets `403` → firmware
   should back off silently.
8. Re-enable → next upload succeeds and device returns to Online.

If all eight pass, the firmware is ready.

## 5. Security expectations for the device

- `X-API-Key` MUST be sent over HTTPS. Never HTTP in production — the key is
  as sensitive as a password.
- Store the key in an area not readable via the debug port if the hardware
  supports it (ESP32 eFuse, secure element, encrypted NVS).
- If you suspect a key is compromised, tell the admin to **rotate** it in the
  dashboard — the device gets the new key on its next visit or via OTA.
- The server rejects `HS256` JWTs (algorithm-confusion prevention); this only
  matters for the human dashboard, not devices.
