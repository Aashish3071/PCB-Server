# Connecting a PCB / Hardware Device to the Server

This is the **end-to-end procedure** to get a physical device reporting to the
PCB Server — from a blank device to a green **Online** status in the dashboard.
It works for the Solar Street Light RMS controller or *any* hardware that can
make an HTTPS request.

For the deep firmware contract (payload fields, response codes, ESP32 /
MicroPython code), see [firmware_integration.md](firmware_integration.md). This
guide is the higher-level flow that ties the dashboard and the device together.

---

## The whole flow at a glance

```
  ADMIN (dashboard)                        DEVICE (hardware)
 ┌──────────────────┐                     ┌────────────────────┐
 │ 1. Create a      │                     │                    │
 │    customer      │                     │                    │
 │ 2. Provision the │  ── UID + API key ──▶ 3. Store the UID + │
 │    device        │      (shown once)   │    API key on the  │
 │                  │                     │    device          │
 │                  │                     │ 4. POST telemetry  │
 │ 5. Device turns  │ ◀── telemetry ──────│    every N seconds │
 │    ONLINE, data  │                     │    (2 headers +    │
 │    appears       │ ─ next_upload_secs ─▶    1 JSON body)    │
 └──────────────────┘                     └────────────────────┘
```

Only **three things** ever travel to the device: the endpoint URL and two
headers (`X-Device-UID`, `X-API-Key`). Everything else is the device reading its
own sensors and posting JSON.

---

## Step 1 — Create a customer (admin, one-time per client)

1. Log in to the dashboard as an admin.
2. **Customers → Add Customer**. Fill in company / contact details, **Save**.

A device must belong to a customer (this is what enforces data isolation — a
customer only ever sees their own devices).

## Step 2 — Provision the device (admin)

1. **Devices → Add Device**.
2. Pick the customer from Step 1.
3. Give it a **Device Name** and optional **Installation Location**.
4. Click **Provision Device**.

The server now shows two strings **exactly once**:

| Field | Looks like | What it is |
|-------|-----------|------------|
| **Device UID** | `SLRMS-000042` | Public identifier for the device |
| **API Key** | `2fb3b3…` (32 chars) | The device's secret — treat like a password |

> ⚠️ **Copy the API Key now.** It is shown in plaintext only at this moment.
> After you close the modal it is stored only as a hash and can never be shown
> again — if lost, you must **rotate** it (a new key is issued, the old one dies).
> You must tick the acknowledgment box before the modal will close.

## Step 3 — Put the credentials on the device

Store two values on the hardware (flash them, or write to NVS/EEPROM):

- `DEVICE_UID` = the UID from Step 2
- `API_KEY` = the API key from Step 2

And point the firmware at the telemetry endpoint:

```
https://<YOUR_BACKEND_DOMAIN>/api/v1/telemetry
```

## Step 4 — Test the connection *before* writing firmware (recommended)

You don't need finished firmware to prove the device credentials work. From a
laptop, phone, or the device's own shell, send one reading with `curl`. If this
succeeds, the hardware just has to reproduce this same request:

```bash
curl -i -X POST https://<YOUR_BACKEND_DOMAIN>/api/v1/telemetry \
  -H "X-Device-UID: SLRMS-000042" \
  -H "X-API-Key: <the-api-key-from-step-2>" \
  -H "Content-Type: application/json" \
  -d '{
        "timestamp": "2026-07-06T10:30:00Z",
        "battery_percentage": 78.5,
        "battery_voltage": 12.6,
        "panel_voltage": 18.4,
        "temperature": 38.2,
        "signal_strength": 65
      }'
```

Expected response:

```json
{ "status": "accepted", "server_time": "…", "next_upload_seconds": 300 }
```

The only field that's **required** is `timestamp` (UTC ISO-8601, ending in `Z`).
Every sensor field is optional — send what the device has, omit the rest.

## Step 5 — Have the device loop forever

Real firmware just repeats Step 4 on a timer. The loop is:

```
wake → read sensors → POST telemetry → read next_upload_seconds → sleep that long → repeat
```

The device **must read `next_upload_seconds` from every response and sleep that
long**. That single field is how the dashboard controls the hardware: change a
device's Upload Interval in the UI and the next response retunes it — **no
reflash**. Working reference code (ESP32/Arduino and MicroPython) is in
[firmware_integration.md §3](firmware_integration.md#3-reference-implementations),
and the [`simulator/`](../simulator/) is a full working Python implementation.

## Step 6 — Verify it's connected (admin)

1. **Devices** — the device status flips from `PROVISIONED` to **`ONLINE`** on
   its first successful telemetry.
2. Click the row → **Device Details**: Battery / Voltage / Signal populate and
   update on each upload.
3. **Fleet Telemetry** shows the historical readings.

That's a connected device. 🎉

## Step 7 — (Optional) Tune how often it reports

**Devices → ⋯ → Edit → Upload Interval (seconds)** — set anywhere from 30 to
86400. The device adopts the new cadence on its next upload via
`next_upload_seconds`. The offline watchdog scales automatically: a device is
flagged **Offline** after 3 missed intervals.

---

## Quick troubleshooting

| Symptom | Response code | What it means / fix |
|---------|--------------|---------------------|
| Device stays `PROVISIONED` | — | It hasn't sent a successful upload yet. Run the Step 4 `curl` to isolate device-vs-firmware. |
| `401 Unauthorized` | 401 | Wrong/unknown UID or API key. Re-check the values; rotate the key if lost. **Don't retry in a tight loop.** |
| `403 Forbidden` | 403 | The device is **Disabled** in the dashboard. Re-enable it from Device Details. |
| `422 Unprocessable` | 422 | Payload malformed — usually a bad `timestamp` (must be UTC ISO-8601 with `Z`) or a sensor value out of range. |
| `429 Too Many Requests` | 429 | Uploading faster than allowed. Read the `Retry-After` header and wait. Almost always a firmware bug ignoring `next_upload_seconds`. |
| Goes `OFFLINE` after being online | — | Power/signal loss, or it stopped uploading. It auto-returns to Online (and auto-resolves the offline alert) on the next successful upload. |

Full response-code contract: [firmware_integration.md §2](firmware_integration.md#response-codes-and-what-firmware-should-do).

---

## Security reminders for whoever connects hardware

- The endpoint is **HTTPS only** in production — the API key is a bearer secret
  and must never cross plain HTTP.
- The API key is per-device. If one device is compromised, rotate **only** that
  device's key; the rest are unaffected.
- Never hardcode the key in a public place (git, forums, screenshots). It lives
  on the device and in the admin's password manager — nowhere else.
