# ClimaTrack — IoT Environmental Monitoring Platform

Collects and visualises temperature, humidity and other sensor metrics from IoT
devices over **MQTT/TLS** and **HTTPS**, with live dashboards and threshold alarms.

Based on **ThingsBoard Community Edition 4.3.1.6** (Apache License 2.0), rebranded at
image build time and run with Docker behind a Traefik HTTPS proxy.

## What's included

| Path | Purpose |
|---|---|
| `docker-compose.yml` | Platform, PostgreSQL 16, Traefik (HTTPS + MQTT/TLS) |
| `branding/` | Brand settings, logos, build-time patcher, Dockerfile, licence notices |
| `proxy/dynamic.yml` | HTTPS and MQTT/TLS routing, security headers |
| `scripts/setup.sh` | One-command install: build, database init, start, provisioning |
| `scripts/deploy.sh` | Deploy to a cloud server over SSH with a Let's Encrypt certificate |
| `scripts/provision.py` | Creates the tenant, admin user, device profile, alarm rules, devices and dashboard |
| `scripts/simulate.py` | Simulated sensors (MQTT/HTTP, optionally over TLS) for demos and testing |
| `scripts/gen-local-certs.sh` | Local test CA + certificate for HTTPS testing without a domain |
| `firmware/esp32_dht22/` | Example ESP32 + DHT22 firmware |
| `.env` *(generated, secret)* | Database password, version, domain and TLS mode |
| `credentials*.json` *(generated, secret)* | Admin logins and device access tokens |

## Network layout

| Port | Exposed | Use |
|---|---|---|
| 443 | public | Web UI and HTTPS device API (`https://DOMAIN/api/v1/<token>/telemetry`) |
| 8883 | public | MQTT over TLS for devices |
| 80 | public | Redirects to HTTPS; Let's Encrypt validation |
| 8080, 1883 | server loopback only | Plain HTTP/MQTT for admin scripts on the server itself |

## Branding

All brand settings live in `branding/brand.json` (product name, company name, version shown on
dashboards, primary colour) and `branding/assets/` (logos, favicon). They are applied when the
image is built:

```bash
docker compose build thingsboard && docker compose up -d
```

What gets rebranded: browser title, favicon, logos (login page, side bar), theme colour, footer
copyright, "Powered by …" on dashboards, two-factor-auth issuer name, share texts, and all e-mail
templates (activation, password reset, etc.). Hidden: the GitHub badge and the *Mobile center*
menu (CSS in `patch_brand.py`), and the home-page "Connect mobile app" QR code, which pointed to
the upstream app (platform setting applied by `provision.py`). In-app help links still
point to the upstream documentation.

The patcher fails the build if any expected string is missing (e.g. after a version change),
so a partially branded image can't ship unnoticed.

## Install and test locally (HTTPS with a local test CA)

Requires Docker (4 GB RAM available to Docker) and Python 3.

```bash
./scripts/setup.sh
python3 scripts/simulate.py --backfill 24                           # history + live data (loopback)
python3 scripts/simulate.py --secure --cafile proxy/certs/ca.crt    # devices via HTTPS + MQTT/TLS
```

Open `https://localhost` and log in with **tenantAdmin** from `credentials.json`. The local
certificate is signed by `proxy/certs/ca.crt`, which browsers don't trust, so expect a warning
(continue anyway for testing; the cloud deployment uses a real certificate).
`http://127.0.0.1:8080` serves the same UI without TLS on this machine.

## Test with real devices on your local network

Devices on the same Wi-Fi/LAN as this computer can send data to it directly. `TB_BIND=0.0.0.0`
in `.env` opens the plain ports to the network (remove it, or never set it, on a cloud server).

| Device setting | Plain (simplest) | Encrypted |
|---|---|---|
| MQTT host / port | `<this computer's LAN IP>` : `1883` | `<LAN IP>` : `8883` + trust `proxy/certs/ca.crt` |
| HTTP endpoint | `http://<LAN IP>:8080/api/v1/<token>/telemetry` | `https://<LAN IP>/api/v1/<token>/telemetry` + CA |
| MQTT username | device access token (password empty) | same |
| MQTT topic | `v1/devices/me/telemetry` | same |

Find the LAN IP with `ipconfig getifaddr en0` (macOS). Things to keep in mind:

- The computer must stay awake and Docker running; e.g. run `caffeinate -dims` in a terminal while testing.
- If the LAN IP changes (DHCP), update the devices and rerun `./scripts/gen-local-certs.sh` +
  `docker compose restart proxy`. A DHCP reservation on the router avoids this.
- Guest Wi-Fi networks often isolate clients from each other; use the main network.
- Devices outside your network can't reach this computer — use the cloud deployment for that.

## Deploy to a cloud server

1. Create a Linux VM (Ubuntu 24.04, **2 vCPU / 4 GB RAM minimum**, 8 GB recommended, 30 GB disk)
   with any provider (AWS Lightsail/EC2, DigitalOcean, Hetzner, Azure, GCP…).
2. Allow inbound **22, 80, 443, 8883** in its firewall / security group, and add your SSH key.
3. From this folder:

```bash
./scripts/deploy.sh ubuntu@<server-ip> you@yourcompany.com              # → https://<ip-with-dashes>.sslip.io
./scripts/deploy.sh ubuntu@<server-ip> you@yourcompany.com iot.example.com   # with your own domain (DNS A record → server IP)
```

The script installs Docker if needed, copies the project, builds the branded image, obtains a Let's
Encrypt certificate, provisions everything and copies the new logins to `credentials.cloud.json`.
Test devices against it from your machine:

```bash
python3 scripts/simulate.py --credentials credentials.cloud.json --secure --backfill 24
```

`sslip.io` gives a working HTTPS address without buying a domain — fine for testing; use your own
domain for the client's production system.

## What gets provisioned

- **Device profile "Environmental Sensor"** — all sensors use it.
- **Dashboard "Environmental Monitoring"** — latest-readings table, time-series charts for
  temperature, humidity, pressure and CO₂ (one line per device), alarms table. Edit it in the UI
  (Edit mode); `provision.py --recreate-dashboard` restores the default layout.
- **Alarm rules** (Calculated fields → alarm rules on the profile):

  | Alarm | Condition | Severity | Per-device override attribute |
  |---|---|---|---|
  | High Temperature | temperature > 35 °C | Major | `temperatureHighThreshold` |
  | Low Temperature | temperature < 5 °C | Major | `temperatureLowThreshold` |
  | High Humidity | humidity > 80 % | Warning | `humidityHighThreshold` |
  | Low Battery | battery < 20 % | Minor | `batteryLowThreshold` |

  To change a limit for one device, add a **server attribute** with the name above on that device
  (Entities → Devices → device → Attributes). Alarms clear automatically when readings return to normal.

The **sysadmin** account manages the platform itself (tenants, mail server, security settings) —
keep it for the operator, not the end client.

## Connecting devices

Each device authenticates with its **access token** (in `credentials*.json`, or
Entities → Devices → device → *Copy access token*). Send any JSON numbers; the keys
`temperature`, `humidity`, `pressure`, `co2`, `battery` appear on the dashboard automatically,
other keys are stored and can be added to widgets.

**MQTT over TLS** — host `DOMAIN`, port `8883`, username = access token, no password:

```bash
mosquitto_pub -h DOMAIN -p 8883 --capath /etc/ssl/certs -u "$TOKEN" \
  -t v1/devices/me/telemetry -m '{"temperature":23.4,"humidity":51.2}'
```

**HTTPS**:

```bash
curl -X POST "https://DOMAIN/api/v1/$TOKEN/telemetry" \
  -H "Content-Type: application/json" -d '{"temperature":23.4,"humidity":51.2}'
```

With a device timestamp (milliseconds): `{"ts":1760000000000,"values":{"temperature":23.4}}`.
An array of such objects uploads buffered readings in one request.

The ESP32 example in `firmware/` uses plain MQTT for simplicity; for the cloud use
`WiFiClientSecure` with the ISRG Root X1 CA certificate and port 8883.

Add devices in the UI (Entities → Devices → +, profile *Environmental Sensor*) or rerun
`provision.py --devices N`.

## Operations

```bash
docker compose ps                     # status
docker compose logs -f thingsboard    # platform logs
docker compose logs -f proxy          # HTTPS / certificate logs
docker compose down                   # stop (data is kept in Docker volumes)
docker compose up -d                  # start
```

**Backup:** `docker compose exec -T postgres pg_dump -U postgres thingsboard | gzip > backup.sql.gz`

## Before handing over to production

1. Use the client's own domain and a real contact e-mail for Let's Encrypt.
2. Configure the outgoing mail server (sysadmin → Settings → Mail server) so alarm notifications
   and password resets work.
3. Change the generated passwords after first login, or create named users for the client.
4. Schedule database backups (and VM snapshots).
5. Replace the placeholder company name in `branding/brand.json` and `branding/NOTICE.txt`, and
   check the product name is free to use as a trademark in your market.

## Licensing

ThingsBoard **4.3.1.6 and earlier are Apache License 2.0**, which permits commercial use,
modification and redistribution. `branding/NOTICE.txt` and `branding/LICENSE-thingsboard-apache-2.0.txt`
are shipped inside the image (`/usr/share/thingsboard/legal/`); keep them with any distribution.
Source-file copyright headers and the web UI's third-party licence list are left unchanged.

**Do not upgrade to ThingsBoard 4.4.0 or later without reviewing its licence.** From 4.4.0
ThingsBoard is under the Business Source License 1.1: free commercial production use is limited
to ≤100 devices on one server, requires a ThingsBoard-issued licence key and visible ThingsBoard
branding (which conflicts with this rebranding); beyond that a paid licence is required.
`TB_VERSION` in `.env` is pinned to 4.3.1.6 for this reason.
