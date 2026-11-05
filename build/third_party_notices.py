"""Generate the third-party notices shipped with the desktop app.

Lists exactly what the .exe distributes:
- frontend: npm packages that end up in the Vite bundle (recorded by the `bundled-packages` plugin in
  vite.config.ts during `npm run build`) plus packages pulled in by CSS `@import` in src/index.css
  (Tailwind, fonts Inter/Fraunces — OFL —, tw-animate-css, shadcn styles);
- backend: the runtime dependency closure of pyproject.toml `[project].dependencies`, read with
  importlib.metadata from the interpreter running this script (the build venv), minus the packages
  excluded in cafeteria.spec;
- runtime: CPython itself (its LICENSE.txt includes OpenSSL, SQLite, libffi, …), the PyInstaller
  bootloader and the Microsoft runtimes pywebview ships.

Output (default build/generated/): THIRD_PARTY_NOTICES.txt (human readable, full texts) and
third_party_notices.json (what Configuración → Acerca de → Licencias de terceros shows).
Copyleft licenses (GPL/LGPL/AGPL/MPL/EPL/…) and packages without a license are flagged on stdout and in
the files; the script never fails because of them (use --strict to make it exit 1).

No third-party dependencies: stdlib only (uses `packaging` for environment markers when available).
Usage: <venv>/python build/third_party_notices.py [--out DIR] [--strict]
"""

from __future__ import annotations

import argparse
import importlib.metadata as md
import json
import re
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
BUNDLED_LIST = FRONTEND / "node_modules" / ".cache" / "bloom" / "bundled-packages.json"

# Keep in sync with `excludes` in cafeteria.spec: installed in the venv but not shipped.
SPEC_EXCLUDED = {
    "cython", "setuptools", "httptools", "websockets", "watchfiles", "pyyaml", "python-dotenv",
    "pydantic-settings", "httpx", "httpcore", "pygments", "pytest", "pyinstaller",
}
# Licenses that impose obligations beyond attribution: reported, never changed automatically.
COPYLEFT = re.compile(r"\b(A?GPL|LGPL|MPL|EPL|CDDL|EUPL|SSPL|CC-BY-SA|OSL)\b|General Public|Mozilla Public", re.I)
LICENSE_FILE = re.compile(r"^(LICEN[CS]E|COPYING|NOTICE|COPYRIGHT|OFL)([.\-_].*)?$", re.I)
COPYRIGHT_LINE = re.compile(r"^\s*(?:\(c\)|©)?\s*copyright\b.*\d{4}.*$", re.I | re.M)

MIT_TEMPLATE = """MIT License

Copyright (c) the {name} authors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO
EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE."""

CLASSIFIER_SPDX = {
    "MIT License": "MIT",
    "BSD License": "BSD",
    "Apache Software License": "Apache-2.0",
    "ISC License (ISCL)": "ISC",
    "Python Software Foundation License": "PSF-2.0",
    "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
    "GNU General Public License v2 (GPLv2)": "GPL-2.0",
    "GNU Lesser General Public License v2 or later (LGPLv2+)": "LGPL-2.0-or-later",
    "The Unlicense (Unlicense)": "Unlicense",
}


def _copyrights(text: str) -> list[str]:
    seen: list[str] = []
    for m in COPYRIGHT_LINE.finditer(text or ""):
        line = " ".join(m.group(0).split())
        if len(line) < 200 and line not in seen:
            seen.append(line)
    return seen[:6]


def _guess_from_text(text: str) -> str:
    """SPDX id from a license text, for packages whose metadata does not declare one."""
    head = " ".join((text or "")[:3000].split())
    if "Permission is hereby granted, free of charge" in head:
        return "MIT"
    if "Permission to use, copy, modify, and/or distribute" in head:
        return "ISC"
    if "Redistribution and use in source and binary forms" in head:
        return "BSD-3-Clause" if "Neither the name" in head else "BSD-2-Clause"
    if "Apache License" in head and "Version 2.0" in head:
        return "Apache-2.0"
    if "SIL OPEN FONT LICENSE" in head.upper():
        return "OFL-1.1"
    return ""


def _entry(name: str, version: str, license_: str, source: str, text: str, homepage: str = "", note: str = "") -> dict:
    license_ = (license_ or "").strip() or _guess_from_text(text) or "Desconocida"
    if not text.strip() and license_ == "MIT":
        note = note or "El paquete no incluye el archivo de licencia: se reproduce el texto estándar de la licencia MIT."
        text = MIT_TEMPLATE.format(name=name)
    return {
        "name": name,
        "version": version,
        "license": license_,
        "source": source,
        "homepage": homepage,
        "copyright": _copyrights(text),
        "text": text.strip(),
        "note": note,
        "copyleft": bool(COPYLEFT.search(license_)),
    }


# --- frontend -----------------------------------------------------------------------------------

def _css_imports() -> set[str]:
    css = (FRONTEND / "src" / "index.css").read_text(encoding="utf-8")
    names = set()
    for spec in re.findall(r'@import\s+["\']([^"\']+)["\']', css):
        if spec.startswith((".", "/")):
            continue
        parts = spec.split("/")
        names.add("/".join(parts[:2]) if spec.startswith("@") else parts[0])
    return names


def _npm_license(pkg: dict) -> str:
    lic = pkg.get("license")
    if isinstance(lic, dict):
        lic = lic.get("type")
    if not lic and isinstance(pkg.get("licenses"), list):
        lic = " OR ".join(x.get("type", "") for x in pkg["licenses"] if isinstance(x, dict))
    return str(lic or "")


def _read_license_files(folder: Path) -> str:
    texts = []
    for f in sorted(folder.iterdir()):
        if f.is_file() and LICENSE_FILE.match(f.name):
            texts.append(f.read_text(encoding="utf-8", errors="replace").strip())
    return "\n\n".join(texts)


def frontend_packages() -> list[dict]:
    if not BUNDLED_LIST.exists():
        raise SystemExit(f"Falta {BUNDLED_LIST}: corré `npm run build` en frontend/ antes de este script.")
    names = set(json.loads(BUNDLED_LIST.read_text(encoding="utf-8"))) | _css_imports()
    out = []
    for name in sorted(names):
        folder = FRONTEND / "node_modules" / name
        if not (folder / "package.json").exists():
            print(f"  ! {name}: no está en node_modules", file=sys.stderr)
            continue
        pkg = json.loads((folder / "package.json").read_text(encoding="utf-8"))
        homepage = pkg.get("homepage") or ""
        repo = pkg.get("repository")
        if not homepage and repo:
            homepage = repo.get("url", "") if isinstance(repo, dict) else str(repo)
        out.append(_entry(name, pkg.get("version", ""), _npm_license(pkg), "frontend",
                          _read_license_files(folder), homepage))
    return out


# --- backend ------------------------------------------------------------------------------------

_REQ = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[([^\]]*)\])?\s*([^;]*)(?:;(.*))?$")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _marker_ok(marker: str | None, extras: set[str]) -> bool:
    if not marker:
        return True
    try:
        from packaging.markers import Marker
    except ImportError:  # no packaging: only honour `extra == ...`
        found = re.findall(r'extra\s*==\s*["\']([^"\']+)["\']', marker)
        return not found or any(e in extras for e in found)
    m = Marker(marker)
    if "extra" in marker:
        return any(m.evaluate({"extra": e}) for e in extras) if extras else False
    return m.evaluate()


def _parse_req(req: str) -> tuple[str, set[str], str | None]:
    m = _REQ.match(req)
    if not m:
        return req.strip(), set(), None
    extras = {e.strip() for e in (m.group(2) or "").split(",") if e.strip()}
    return m.group(1), extras, (m.group(4) or "").strip() or None


def _dist_license(dist: md.Distribution) -> str:
    meta = dist.metadata
    expr = meta.get("License-Expression")
    if expr:
        return expr
    lic = (meta.get("License") or "").strip()
    if lic and "\n" not in lic and len(lic) < 80:
        return lic
    found = []
    for c in meta.get_all("Classifier") or []:
        if c.startswith("License :: "):
            last = c.split(" :: ")[-1]
            found.append(CLASSIFIER_SPDX.get(last, last))
    return " OR ".join(dict.fromkeys(found)) or ("Ver texto" if lic else "")


def _dist_text(dist: md.Distribution) -> str:
    texts = []
    for f in dist.files or []:
        name = Path(str(f)).name
        if ".dist-info" in str(f) and LICENSE_FILE.match(name):
            try:
                texts.append(Path(dist.locate_file(f)).read_text(encoding="utf-8", errors="replace").strip())
            except OSError:
                pass
    if not texts:
        lic = (dist.metadata.get("License") or "").strip()
        if "\n" in lic or len(lic) >= 80:
            texts.append(lic)
    return "\n\n".join(dict.fromkeys(texts))


def backend_packages() -> list[dict]:
    project = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    queue = [_parse_req(r)[:2] for r in project["dependencies"]]
    seen: dict[str, md.Distribution] = {}
    while queue:
        name, extras = queue.pop()
        key = _norm(name)
        if key in SPEC_EXCLUDED:
            continue
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            print(f"  ! {name}: no está instalado (se omite)", file=sys.stderr)
            continue
        first = key not in seen
        seen[key] = dist
        for req in dist.requires or []:
            dep, dep_extras, marker = _parse_req(req)
            if _marker_ok(marker, extras) and (first or extras):
                queue.append((dep, dep_extras))
    out = []
    for key in sorted(seen):
        dist = seen[key]
        meta = dist.metadata
        homepage = meta.get("Home-page") or ""
        for url in meta.get_all("Project-URL") or []:
            if not homepage or url.lower().startswith(("homepage", "source", "repository")):
                homepage = url.split(",", 1)[-1].strip()
                break
        out.append(_entry(meta["Name"], dist.version, _dist_license(dist), "backend", _dist_text(dist), homepage))
    return out


# --- runtime (not discoverable as packages) ----------------------------------------------------

def runtime_components() -> list[dict]:
    out = []
    py_license = Path(sys.base_prefix) / "LICENSE.txt"
    out.append(_entry(
        "Python (CPython)", sys.version.split()[0], "PSF-2.0", "runtime",
        py_license.read_text(encoding="utf-8", errors="replace") if py_license.exists() else "",
        "https://www.python.org/",
        "Incluye OpenSSL, SQLite, libffi, bzip2, xz y zlib (sus avisos están en este mismo texto).",
    ))
    try:
        dist = md.distribution("pyinstaller")
        out.append(_entry(
            "PyInstaller bootloader", dist.version, "GPL-2.0-or-later WITH Bootloader-exception", "runtime",
            _dist_text(dist), "https://pyinstaller.org/",
            "Solo el cargador del .exe. La excepción del bootloader permite distribuirlo con programas de "
            "cualquier licencia; el resto de PyInstaller no se distribuye.",
        ))
    except md.PackageNotFoundError:
        pass
    out.append(_entry(
        "Microsoft Visual C++ Runtime / WebView2 SDK", "", "Microsoft (redistribuible)", "runtime",
        "VCRUNTIME140.dll, ucrtbase.dll y Microsoft.Web.WebView2.*.dll (incluidos por Python y pywebview) "
        "se redistribuyen según los términos de licencia de Microsoft para componentes redistribuibles.\n"
        "Copyright (c) Microsoft Corporation. All rights reserved.",
        "https://learn.microsoft.com/microsoft-edge/webview2/",
    ))
    return out


# --- output -------------------------------------------------------------------------------------

def render_text(app: str, packages: list[dict]) -> str:
    lines = [
        f"{app} — Avisos de software de terceros",
        "=" * 60,
        "",
        f"{app} incluye los siguientes componentes de terceros. Cada uno se distribuye bajo su propia",
        "licencia, cuyo texto se reproduce más abajo.",
        "",
    ]
    for p in packages:
        lines.append(f"- {p['name']} {p['version']} ({p['source']}) — {p['license']}")
    for p in packages:
        lines += ["", "-" * 60, f"{p['name']} {p['version']}", f"Licencia: {p['license']}"]
        if p["homepage"]:
            lines.append(f"Sitio: {p['homepage']}")
        if p["note"]:
            lines.append(p["note"])
        lines += ["", p["text"] or "(El paquete no incluye el texto de la licencia.)"]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "build" / "generated")
    ap.add_argument("--strict", action="store_true", help="exit 1 if a copyleft or unknown license is found")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    brand = json.loads((ROOT / "brand.json").read_text(encoding="utf-8"))
    packages = runtime_components() + backend_packages() + frontend_packages()
    flagged = [p for p in packages if p["copyleft"] or p["license"] == "Desconocida"]
    missing_text = [p["name"] for p in packages if not p["text"]]

    args.out.mkdir(parents=True, exist_ok=True)
    data = {
        "app": brand.get("name", "Bloom"),
        "version": brand.get("version", ""),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "packages": packages,
        "flagged": [{"name": p["name"], "license": p["license"], "note": p["note"]} for p in flagged],
    }
    (args.out / "third_party_notices.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (args.out / "THIRD_PARTY_NOTICES.txt").write_text(render_text(data["app"], packages), encoding="utf-8")

    by_source = {s: sum(1 for p in packages if p["source"] == s) for s in ("runtime", "backend", "frontend")}
    print(f"Avisos de terceros: {len(packages)} componentes {by_source} -> {args.out}")
    for p in flagged:
        print(f"  ATENCIÓN {p['name']} {p['version']}: {p['license']}")
    if missing_text:
        print(f"  Sin texto de licencia en el paquete: {', '.join(missing_text)}")
    return 1 if args.strict and flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
