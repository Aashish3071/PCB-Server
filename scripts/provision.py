#!/usr/bin/env python3
"""Provision a fresh ThingsBoard CE instance for environmental monitoring.

Steps (idempotent per run on a fresh install):
  1. Replace the default system-administrator password.
  2. Create the client tenant and its tenant administrator.
  3. Create the "Environmental Sensor" device profile and its alarm rules.
  4. Create sensor devices and collect their access tokens.
  5. Create the "Environmental Monitoring" dashboard.

Generated secrets are written to credentials.json (git-ignored, mode 600).
Only the Python standard library is used.

Usage:
  python3 scripts/provision.py [--url http://localhost:8080] [--tenant "Client Org"]
                               [--admin-email admin@client.local] [--devices 3]
"""
import argparse
import json
import os
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(ROOT, "credentials.json")
PROFILE_NAME = "Environmental Sensor"
DASHBOARD_TITLE = "Environmental Monitoring"

# Telemetry keys the platform is set up to display: (key, label, units, color, decimals)
METRICS = [
    ("temperature", "Temperature", "°C", "#E65100", 1),
    ("humidity", "Humidity", "%", "#0277BD", 1),
    ("pressure", "Pressure", "hPa", "#6A1B9A", 1),
    ("co2", "CO₂", "ppm", "#2E7D32", 0),
    ("battery", "Battery", "%", "#546E7A", 0),
]

# Alarm rules: (id, alarm type, key, operation, default threshold, threshold attribute, severity)
# The threshold can be overridden per device with a server-side attribute of the given name.
ALARMS = [
    ("highTemperature", "High Temperature", "temperature", "GREATER", 35, "temperatureHighThreshold", "MAJOR"),
    ("lowTemperature", "Low Temperature", "temperature", "LESS", 5, "temperatureLowThreshold", "MAJOR"),
    ("highHumidity", "High Humidity", "humidity", "GREATER", 80, "humidityHighThreshold", "WARNING"),
    ("lowBattery", "Low Battery", "battery", "LESS", 20, "batteryLowThreshold", "MINOR"),
]
OPPOSITE = {"GREATER": "LESS_OR_EQUAL", "LESS": "GREATER_OR_EQUAL"}


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.token = None

    def call(self, method, path, body=None, params=None):
        url = self.base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.token:
            req.add_header("X-Authorization", "Bearer " + self.token)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"{method} {path} failed: HTTP {e.code} {e.read().decode(errors='replace')}")
        return json.loads(raw) if raw else None

    def login(self, username, password):
        self.token = None
        self.token = self.call("POST", "/api/auth/login", {"username": username, "password": password})["token"]


def gen_password():
    # Meets ThingsBoard's default policy and is easy to copy.
    return secrets.token_urlsafe(14) + "A9!"


def secure_sysadmin(api, creds):
    sysadmin = creds.setdefault("sysadmin", {"email": "sysadmin@thingsboard.org"})
    if "password" in sysadmin:
        api.login(sysadmin["email"], sysadmin["password"])
        return
    api.login(sysadmin["email"], "sysadmin")
    new_password = gen_password()
    api.call("POST", "/api/auth/changePassword", {"currentPassword": "sysadmin", "newPassword": new_password})
    sysadmin["password"] = new_password
    save(creds)
    api.login(sysadmin["email"], new_password)
    print("✓ System administrator password replaced")


def set_base_url(api, public_url):
    """Links in e-mails (activation, password reset) use the platform's public address."""
    general = api.call("GET", "/api/admin/settings/general")
    if general["jsonValue"].get("baseUrl") != public_url:
        general["jsonValue"]["baseUrl"] = public_url
        general["jsonValue"]["prohibitDifferentUrl"] = False
        api.call("POST", "/api/admin/settings", general)
        print(f"✓ Platform base URL set to {public_url}")


def disable_mobile_app(api):
    """Hide the home-page "Connect mobile app" QR code; it links to the upstream ThingsBoard app."""
    qr = api.call("GET", "/api/mobile/qr/settings")
    if qr["qrCodeConfig"]["showOnHomePage"] or qr["androidEnabled"] or qr["iosEnabled"]:
        qr["qrCodeConfig"]["showOnHomePage"] = False
        qr["androidEnabled"] = False
        qr["iosEnabled"] = False
        api.call("POST", "/api/mobile/qr/settings", qr)
        print("✓ Mobile app QR code and app links disabled")


def create_tenant(api, creds, title, admin_email):
    tenant = creds.setdefault("tenant", {})
    if "id" not in tenant:
        t = api.call("POST", "/api/tenant", {"title": title})
        tenant.update({"id": t["id"]["id"], "title": title})
        save(creds)
        print(f"✓ Tenant '{title}' created")
    admin = creds.setdefault("tenantAdmin", {})
    if "password" not in admin:
        user = api.call("POST", "/api/user", {
            "tenantId": {"id": tenant["id"], "entityType": "TENANT"},
            "email": admin_email,
            "authority": "TENANT_ADMIN",
            "firstName": "Client",
            "lastName": "Administrator",
        }, params={"sendActivationMail": "false"})
        link = api.call("GET", f"/api/user/{user['id']['id']}/activationLinkInfo")
        token = urllib.parse.parse_qs(urllib.parse.urlparse(link["value"]).query)["activateToken"][0]
        password = gen_password()
        api.call("POST", "/api/noauth/activate", {"activateToken": token, "password": password},
                 params={"sendActivationMail": "false"})
        admin.update({"email": admin_email, "password": password})
        save(creds)
        print(f"✓ Tenant administrator {admin_email} created")


def alarm_condition(key, operation):
    return {"type": "SIMPLE", "expression": {"type": "SIMPLE", "operation": "AND", "filters": [{
        "argument": key,
        "valueType": "NUMERIC",
        "operation": "AND",
        "predicates": [{"type": "NUMERIC", "operation": operation,
                        "value": {"staticValue": None, "dynamicValueArgument": "threshold"}}],
    }]}}


def create_device_profile(api):
    existing = api.call("GET", "/api/deviceProfileInfos", params={"pageSize": 100, "page": 0, "textSearch": PROFILE_NAME})
    for p in existing["data"]:
        if p["name"] == PROFILE_NAME:
            return p["id"]["id"]
    profile = api.call("POST", "/api/deviceProfile", {
        "name": PROFILE_NAME,
        "description": "Temperature / humidity / environmental sensors (MQTT or HTTP)",
        "type": "DEFAULT",
        "transportType": "DEFAULT",
        "provisionType": "DISABLED",
        "profileData": {
            "configuration": {"type": "DEFAULT"},
            "transportConfiguration": {"type": "DEFAULT"},
            "provisionConfiguration": {"type": "DISABLED", "provisionDeviceSecret": None},
        },
    })
    print(f"✓ Device profile '{PROFILE_NAME}' created")
    return profile["id"]["id"]


def create_alarm_rules(api, profile_id):
    """Alarm rules (calculated fields, ThingsBoard 4.3+) evaluated for every device of the profile."""
    existing = api.call("GET", f"/api/alarm/rules/DEVICE_PROFILE/{profile_id}", params={"pageSize": 100, "page": 0})
    names = {r["name"] for r in existing["data"]}
    for _, alarm_type, key, op, threshold, attr, severity in ALARMS:
        if alarm_type in names:
            continue
        api.call("POST", "/api/alarm/rule", {
            "entityId": {"entityType": "DEVICE_PROFILE", "id": profile_id},
            "name": alarm_type,
            "configuration": {
                "type": "ALARM",
                "arguments": {
                    key: {"refEntityKey": {"key": key, "type": "TS_LATEST"}},
                    "threshold": {"refEntityKey": {"key": attr, "type": "ATTRIBUTE", "scope": "SERVER_SCOPE"},
                                  "defaultValue": str(threshold)},
                },
                "createRules": {severity: {"condition": alarm_condition(key, op),
                                           "alarmDetails": f"{key} = ${{{key}}} (threshold ${{threshold}})"}},
                "clearRule": {"condition": alarm_condition(key, OPPOSITE[op])},
                "propagate": False,
            },
        })
        print(f"✓ Alarm rule '{alarm_type}' ({key} {op} {threshold}, per-device attribute '{attr}')")


def create_devices(api, creds, profile_id, count):
    devices = creds.setdefault("devices", {})
    for i in range(1, count + 1):
        name = f"Sensor-{i:03d}"
        if name in devices:
            continue
        device = api.call("POST", "/api/device", {
            "name": name,
            "label": f"Environmental sensor {i}",
            "deviceProfileId": {"id": profile_id, "entityType": "DEVICE_PROFILE"},
        })
        cred = api.call("GET", f"/api/device/{device['id']['id']}/credentials")
        devices[name] = {"id": device["id"]["id"], "accessToken": cred["credentialsId"]}
        save(creds)
        print(f"✓ Device {name} created")


# ---------------------------------------------------------------- dashboard

def widget_defaults(api, fqn):
    wt = api.call("GET", "/api/widgetType", params={"fqn": "system." + fqn})
    desc = wt["descriptor"]
    config = json.loads(desc["defaultConfig"])
    return desc["type"], config


def data_key(name, label, color, units=None, decimals=None, key_type="timeseries"):
    key = {"name": name, "type": key_type, "label": label, "color": color, "settings": {},
           "_hash": secrets.randbelow(10**9) / 10**9}
    if units is not None:
        key["units"] = units
    if decimals is not None:
        key["decimals"] = decimals
    return key


def make_widget(api, fqn, title, size_x, size_y, datasources=None, alarm_source=None, extra=None):
    wtype, config = widget_defaults(api, fqn)
    config["title"] = title
    config["showTitle"] = True
    config["useDashboardTimewindow"] = True
    if datasources is not None:
        config["datasources"] = datasources
    if alarm_source is not None:
        config["alarmSource"] = alarm_source
    if extra:
        config.update(extra)
    # Table widgets render their heading from settings rather than the widget title.
    for heading in ("entitiesTitle", "alarmsTitle"):
        if heading in config.get("settings", {}) or fqn.endswith(heading.replace("Title", "_table")):
            config.setdefault("settings", {})[heading] = title
    return {"typeFullFqn": "system." + fqn, "type": wtype, "sizeX": size_x, "sizeY": size_y, "config": config,
            "row": 0, "col": 0, "id": str(uuid.uuid4())}


def create_dashboard(api, recreate=False):
    existing = api.call("GET", "/api/tenant/dashboards", params={"pageSize": 100, "page": 0, "textSearch": DASHBOARD_TITLE})
    for d in existing["data"]:
        if d["title"] == DASHBOARD_TITLE:
            if not recreate:
                return d["id"]["id"]
            api.call("DELETE", f"/api/dashboard/{d['id']['id']}")

    alias_id = str(uuid.uuid4())
    alias = {alias_id: {
        "id": alias_id,
        "alias": "All sensors",
        "filter": {"type": "deviceType", "resolveMultiple": True, "deviceTypes": [PROFILE_NAME], "deviceNameFilter": ""},
    }}
    entity_ds = lambda keys: [{"type": "entity", "entityAliasId": alias_id, "dataKeys": keys}]

    table_keys = [data_key("name", "Device", "#212121", key_type="entityField")] + \
                 [data_key(k, f"{label} ({units})", color, units, dec) for k, label, units, color, dec in METRICS]
    widgets = [
        (make_widget(api, "cards.entities_table", "Sensors — latest readings", 24, 8, entity_ds(table_keys),
                     extra={"useDashboardTimewindow": False}), 0, 0),
    ]
    row = 8
    for idx, (k, label, units, color, dec) in enumerate(METRICS[:4]):
        w = make_widget(api, "time_series_chart", f"{label} ({units})", 12, 9,
                        entity_ds([data_key(k, "${entityName}", color, units, dec)]))
        widgets.append((w, row + (idx // 2) * 9, (idx % 2) * 12))
    row += 18
    alarm_keys = [data_key(n, l, "#212121", key_type="alarm") for n, l in
                  [("createdTime", "Created"), ("originator", "Device"), ("type", "Type"),
                   ("severity", "Severity"), ("status", "Status")]]
    widgets.append((make_widget(api, "alarm_widgets.alarms_table", "Alarms", 24, 7,
                                datasources=[], alarm_source={"type": "entity", "entityAliasId": alias_id,
                                                              "dataKeys": alarm_keys}), row, 0))

    config_widgets, layout = {}, {}
    for w, r, c in widgets:
        wid = w.pop("id")
        w.pop("row"), w.pop("col")
        config_widgets[wid] = dict(w, id=wid)
        layout[wid] = {"sizeX": w["sizeX"], "sizeY": w["sizeY"], "row": r, "col": c}

    dashboard = api.call("POST", "/api/dashboard", {
        "title": DASHBOARD_TITLE,
        "configuration": {
            "description": "Live temperature, humidity and environmental metrics for all sensors",
            "widgets": config_widgets,
            "entityAliases": alias,
            "filters": {},
            "states": {"default": {"name": DASHBOARD_TITLE, "root": True, "layouts": {"main": {
                "widgets": layout,
                "gridSettings": {"backgroundColor": "#eeeeee", "columns": 24, "margin": 10, "outerMargin": True,
                                 "backgroundSizeMode": "100%"},
            }}}},
            "timewindow": {"displayValue": "", "selectedTab": 0, "realtime": {
                "realtimeType": 0, "timewindowMs": 6 * 3600 * 1000, "interval": 60 * 1000},
                "aggregation": {"type": "AVG", "limit": 25000}},
            "settings": {"stateControllerId": "entity", "showTitle": True, "showDashboardsSelect": True,
                         "showEntitiesSelect": True, "showDashboardTimewindow": True, "showDashboardExport": True,
                         "toolbarAlwaysOpen": True},
        },
    })
    print(f"✓ Dashboard '{DASHBOARD_TITLE}' created")
    return dashboard["id"]["id"]


def save(creds):
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f, indent=2)
    os.chmod(CREDENTIALS_FILE, 0o600)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default="http://localhost:8080", help="admin API address (loopback on the server)")
    ap.add_argument("--public-url", help="address users and devices use, e.g. https://iot.example.com")
    ap.add_argument("--tenant", default="Client Org")
    ap.add_argument("--admin-email", default="admin@client.local")
    ap.add_argument("--devices", type=int, default=3)
    ap.add_argument("--recreate-dashboard", action="store_true", help="replace the dashboard with the current layout")
    args = ap.parse_args()

    creds = {}
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            creds = json.load(f)
    creds["url"] = args.url
    if args.public_url:
        creds["publicUrl"] = args.public_url

    api = Api(args.url)
    secure_sysadmin(api, creds)
    if creds.get("publicUrl"):
        set_base_url(api, creds["publicUrl"])
    disable_mobile_app(api)
    create_tenant(api, creds, args.tenant, args.admin_email)

    api.login(creds["tenantAdmin"]["email"], creds["tenantAdmin"]["password"])
    profile_id = create_device_profile(api)
    create_alarm_rules(api, profile_id)
    create_devices(api, creds, profile_id, args.devices)
    creds["dashboardId"] = create_dashboard(api, args.recreate_dashboard)
    save(creds)
    print(f"\nDone. Logins and device tokens are in {CREDENTIALS_FILE}")
    print(f"Dashboard: {creds.get('publicUrl', args.url)}/dashboards/{creds['dashboardId']}")


if __name__ == "__main__":
    sys.exit(main())
