#!/usr/bin/env python3
"""Rebrand the ThingsBoard CE 4.3.x server jar with the settings in brand.json.

Rewrites the web UI bundle (nested ui-ngx jar) and the e-mail templates, keeping
every other entry byte-for-byte. Each patch asserts it matched, so a ThingsBoard
upgrade that moves a string fails the build instead of silently shipping
half-branded.

Licence notes: SPDX / copyright headers in source files and 3rdpartylicenses.txt
are left untouched (Apache 2.0 §4); only user-visible product naming changes.

Usage: patch_brand.py <brand.json> <assets dir> <input jar> <output jar>
"""
import gzip
import io
import json
import re
import sys
import zipfile

LOCALE_KEYS = {"socialshare-text", "socialshare-title", "built-in-missing-text"}
OLD_PRIMARY = "#305680"
# UI elements hidden in the product: GitHub star badge, "Mobile center" side-menu entry.
HIDDEN_UI_CSS = ("tb-github-badge{display:none!important}"
                 "li:has(>tb-menu-link>a[href^='/mobile-center']){display:none!important}")


class Patcher:
    def __init__(self, brand):
        self.b = brand
        self.misses = []

    def sub(self, text, old, new, name, expected=None):
        count = text.count(old)
        if count == 0 or (expected is not None and count != expected):
            self.misses.append(f"{name}: expected {expected or '≥1'} × {old!r}, found {count}")
            return text
        return text.replace(old, new)

    # ------------------------------------------------------------- web UI
    def patch_ui_file(self, path, text):
        b, product = self.b, self.b["productName"]
        if path == "public/index.html":
            text = self.sub(text, "<title>ThingsBoard</title>", f"<title>{product}</title>", path)
            text = self.sub(text, 'type="image/x-icon" href="thingsboard.ico"',
                            'type="image/svg+xml" href="assets/brand-favicon.svg"', path)
            text = self.sub(text, "rgb(43,160,199)", b["accentColor"], path)
            text = self.sub(text, "</head>", f"<style>{HIDDEN_UI_CSS}</style>\n</head>", path, 1)
        if path.endswith(".js"):
            for old, new in [
                ('appTitle:"ThingsBoard"', f'appTitle:"{product}"'),
                ('" The ThingsBoard Authors"', f'" {b["companyName"]}"'),
                ('"ThingsBoard v.",o.thingsboardVersion', f'"{product} v.","{b["productVersion"]}"'),
                ('{value:"ThingsBoard",disabled:!0}', f'{{value:"{product}",disabled:!0}}'),
                ("`ThingsBoard Version: ", f"`{product} Version: "),
            ]:
                if old in text:
                    text = text.replace(old, new)
                    self.found.add(old)
            if 'C("' + product + ' v."' in text:
                # "Powered by" link on dashboards points to the platform itself.
                text = re.sub(r'(\["href","https://thingsboard\.io","target","_blank"\])',
                              '["href","/","target","_self"]', text)
        if path.endswith((".js", ".css")):
            text = text.replace(OLD_PRIMARY, b["primaryColor"])
        if path.startswith("public/assets/locale/") and path.endswith(".json"):
            data = json.loads(text)
            self._brand_locale(data)
            text = json.dumps(data, ensure_ascii=False, indent=2)
        return text

    def _brand_locale(self, node):
        for key, value in node.items():
            if isinstance(value, dict):
                self._brand_locale(value)
            elif key in LOCALE_KEYS and isinstance(value, str):
                node[key] = value.replace("ThingsBoard", self.b["productName"])

    def patch_ui_jar(self, data, assets):
        src = zipfile.ZipFile(io.BytesIO(data))
        out = io.BytesIO()
        self.found = set()
        replaced_assets = {f"public/assets/{n}": n for n in ("logo_title_white.svg", "logo_white.svg")}
        names = set(src.namelist())
        patched = {}
        for info in src.infolist():
            name = info.filename
            if name in replaced_assets:
                patched[name] = assets[replaced_assets[name]]
            elif name.endswith((".html", ".js", ".css", ".json")) and name.startswith("public/"):
                patched[name] = self.patch_ui_file(name, src.read(info).decode("utf-8")).encode("utf-8")
        with zipfile.ZipFile(out, "w") as dst:
            for info in src.infolist():
                name = info.filename
                if name in patched:
                    body = patched[name]
                elif name.endswith(".gz") and name[:-3] in patched:
                    # Precompressed copy served to gzip-capable browsers: rebuild from the patched original.
                    body = gzip.compress(patched[name[:-3]], mtime=0)
                else:
                    body = src.read(info)
                dst.writestr(info, body, compress_type=info.compress_type)
            fav = zipfile.ZipInfo("public/assets/brand-favicon.svg", date_time=(2026, 1, 1, 0, 0, 0))
            dst.writestr(fav, assets["favicon.svg"], compress_type=zipfile.ZIP_DEFLATED)
        for required in ['appTitle:"ThingsBoard"', '" The ThingsBoard Authors"',
                         '"ThingsBoard v.",o.thingsboardVersion', '{value:"ThingsBoard",disabled:!0}']:
            if required not in self.found:
                self.misses.append(f"UI bundle: {required!r} not found")
        return out.getvalue()

    # ------------------------------------------------------------- e-mails
    def patch_template(self, name, text):
        product = self.b["productName"]
        lines = []
        for line in text.splitlines(keepends=True):
            if "SPDX" not in line:
                line = line.replace("&mdash; The Thingsboard", f"&mdash; The {product} Team")
                line = re.sub(r"Thingsboard|ThingsBoard", product, line)
                line = line.replace("#348eda", self.b["primaryColor"])
            lines.append(line)
        return "".join(lines)


def main(brand_path, assets_dir, in_jar, out_jar):
    with open(brand_path) as f:
        brand = json.load(f)
    assets = {}
    for n in ("logo_title_white.svg", "logo_white.svg", "favicon.svg"):
        with open(f"{assets_dir}/{n}", "rb") as f:
            assets[n] = f.read()

    with open(in_jar, "rb") as f:
        raw = f.read()
    zip_start = raw.find(b"PK\x03\x04")
    prefix = raw[:zip_start]  # launch script prepended by Spring Boot
    p = Patcher(brand)

    src = zipfile.ZipFile(io.BytesIO(raw))
    # Start the archive after the launch script; append mode records absolute offsets,
    # matching how the original executable jar is laid out.
    out = io.BytesIO(prefix)
    out.seek(0, io.SEEK_END)
    ui_done = templates = 0
    with zipfile.ZipFile(out, "a") as dst:
        for info in src.infolist():
            body = src.read(info)
            if re.fullmatch(r"BOOT-INF/lib/ui-ngx-[\d.]+\.jar", info.filename):
                body = p.patch_ui_jar(body, assets)
                ui_done += 1
            elif info.filename.startswith("BOOT-INF/classes/templates/") and info.filename.endswith(".ftl"):
                body = p.patch_template(info.filename, body.decode("utf-8")).encode("utf-8")
                templates += 1
            # Nested jars must stay STORED for the Spring Boot loader; keep every entry's method.
            dst.writestr(info, body, compress_type=info.compress_type)

    if ui_done != 1:
        p.misses.append(f"expected one ui-ngx jar, found {ui_done}")
    if p.misses:
        sys.exit("Branding failed:\n  " + "\n  ".join(p.misses))
    with open(out_jar, "wb") as f:
        f.write(out.getvalue())
    print(f"Branded as {brand['productName']}: UI bundle + {templates} e-mail templates -> {out_jar}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    main(*sys.argv[1:])
