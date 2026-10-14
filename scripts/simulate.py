#!/usr/bin/env python3
"""Simulate environmental sensors sending telemetry over MQTT and HTTP.

Device tokens are read from credentials.json (written by provision.py).
Odd-numbered sensors publish over MQTT, even-numbered over HTTP, so both
device APIs are exercised. Only the Python standard library is used.

Usage:
  python3 scripts/simulate.py                  # send live readings every 10 s
  python3 scripts/simulate.py --backfill 24    # first upload 24 h of history
  python3 scripts/simulate.py --once           # send one reading per sensor and exit
  python3 scripts/simulate.py --spike          # force a high-temperature reading (alarm test)
  python3 scripts/simulate.py --secure         # use the public HTTPS / MQTT-over-TLS endpoints
  python3 scripts/simulate.py --secure --cafile proxy/certs/ca.crt   # same, local test CA
"""
import argparse
import json
import math
import os
import random
import socket
import ssl
import struct
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def reading(device_index, ts_ms, spike=False):
    """Plausible indoor readings with a daily cycle, per-device offset and noise."""
    hour = (ts_ms / 3_600_000) % 24
    daily = math.sin((hour - 9) / 24 * 2 * math.pi)
    offset = device_index * 1.3
    temperature = 22 + offset + 4 * daily + random.gauss(0, 0.3)
    humidity = 55 - 10 * daily - offset + random.gauss(0, 1.0)
    days = ts_ms / 86_400_000
    return {
        "temperature": round(38.5 if spike else temperature, 2),
        "humidity": round(min(max(humidity, 5), 99), 2),
        "pressure": round(1013 + 3 * math.sin(days * 2 * math.pi / 3) + random.gauss(0, 0.2), 2),
        "co2": round(450 + 250 * max(daily, 0) + random.gauss(0, 15)),
        "battery": round(max(100 - (days % 30) * 2.5 - device_index * 3, 0), 1),
    }


# ---------------------------------------------------------------- HTTP device API

def http_send(base_url, token, payload, tls_context=None):
    url = f"{base_url}/api/v1/{urllib.parse.quote(token)}/telemetry"
    req = urllib.request.Request(url, json.dumps(payload).encode(), {"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30, context=tls_context) as resp:
        resp.read()


# ---------------------------------------------------------------- minimal MQTT 3.1.1 (QoS 0)

def _mqtt_str(s):
    b = s.encode()
    return struct.pack("!H", len(b)) + b


def _mqtt_len(n):
    out = bytearray()
    while True:
        byte, n = n % 128, n // 128
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


class MqttDevice:
    """Just enough MQTT to authenticate with a device token and publish telemetry."""

    def __init__(self, host, port, token, client_id, tls_context=None):
        self.sock = socket.create_connection((host, port), timeout=15)
        if tls_context:
            self.sock = tls_context.wrap_socket(self.sock, server_hostname=host)
        var = _mqtt_str("MQTT") + bytes([4, 0x82]) + struct.pack("!H", 60)  # v3.1.1, username + clean session
        body = var + _mqtt_str(client_id) + _mqtt_str(token)
        self.sock.sendall(b"\x10" + _mqtt_len(len(body)) + body)
        ack = self.sock.recv(4)
        if len(ack) < 4 or ack[0] != 0x20 or ack[3] != 0:
            raise ConnectionError(f"MQTT connect refused (CONNACK {ack.hex()})")

    def publish(self, payload, topic="v1/devices/me/telemetry"):
        body = _mqtt_str(topic) + json.dumps(payload).encode()
        self.sock.sendall(b"\x30" + _mqtt_len(len(body)) + body)

    def close(self):
        try:
            self.sock.sendall(b"\xe0\x00")
        finally:
            self.sock.close()


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--credentials", default=os.path.join(ROOT, "credentials.json"))
    ap.add_argument("--secure", action="store_true",
                    help="send to the public address over HTTPS and MQTT/TLS (port 8883)")
    ap.add_argument("--cafile", help="CA certificate to trust (local test CA)")
    ap.add_argument("--mqtt-host", help="default: host of the selected base URL")
    ap.add_argument("--mqtt-port", type=int, help="default: 8883 with --secure, else 1883")
    ap.add_argument("--interval", type=float, default=10, help="seconds between live readings")
    ap.add_argument("--backfill", type=float, default=0, help="hours of history to upload first")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--spike", action="store_true", help="send an over-threshold temperature")
    args = ap.parse_args()

    with open(args.credentials) as f:
        creds = json.load(f)
    base_url = creds.get("publicUrl", creds["url"]) if args.secure else creds["url"]
    tls_context = ssl.create_default_context(cafile=args.cafile) if args.secure else None
    mqtt_host = args.mqtt_host or urllib.parse.urlparse(base_url).hostname
    mqtt_port = args.mqtt_port or (8883 if args.secure else 1883)
    devices = sorted(creds["devices"].items())

    if args.backfill:
        now = int(time.time() * 1000)
        step = 5 * 60 * 1000
        for i, (name, dev) in enumerate(devices):
            history = [{"ts": ts, "values": reading(i, ts)} for ts in range(now - int(args.backfill * 3_600_000), now, step)]
            for chunk in range(0, len(history), 500):
                http_send(base_url, dev["accessToken"], history[chunk:chunk + 500], tls_context)
            print(f"↑ {name}: backfilled {len(history)} readings ({args.backfill:g} h)")

    mqtt = {}
    try:
        while True:
            ts = int(time.time() * 1000)
            for i, (name, dev) in enumerate(devices):
                values = reading(i, ts, spike=args.spike and i == 0)
                if i % 2 == 0:
                    if name not in mqtt:
                        mqtt[name] = MqttDevice(mqtt_host, mqtt_port, dev["accessToken"], name, tls_context)
                    mqtt[name].publish(values)
                    via = "MQTTS" if tls_context else "MQTT"
                else:
                    http_send(base_url, dev["accessToken"], values, tls_context)
                    via = "HTTPS" if base_url.startswith("https") else "HTTP"
                print(f"→ {name} [{via}] {values}")
            if args.once or args.spike:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        for client in mqtt.values():
            client.close()


if __name__ == "__main__":
    sys.exit(main())
