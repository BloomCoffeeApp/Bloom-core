"""Writes the (unsigned) update manifest `latest.json` for a freshly built installer.

    python build/make_manifest.py --installer output/installer/Bloom-Setup-1.2.0.exe --version 1.2.0 \
        --brand ../brand.json --out output/installer/latest.json [--notes "..."] [--url https://...]

The download URL defaults to where the release will host the installer, derived from
brand.json `updateManifest`:
  https://github.com/<owner>/<repo>/releases/latest/download/latest.json
      -> https://github.com/<owner>/<repo>/releases/download/v<version>/<installer name>
  any other https://host/path/latest.json -> https://host/path/<installer name>

The app refuses a manifest without a valid signature: sign it with the vendor's key before
publishing (see README → "Publicar una versión").
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

GITHUB_LATEST = "/releases/latest/download/latest.json"


def default_url(manifest_url: str, version: str, installer_name: str) -> str:
    if not manifest_url:
        return ""
    if manifest_url.endswith(GITHUB_LATEST):
        return f"{manifest_url[: -len(GITHUB_LATEST)]}/releases/download/v{version}/{installer_name}"
    return f"{manifest_url.rsplit('/', 1)[0]}/{installer_name}"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--installer", required=True, type=Path)
    p.add_argument("--version", required=True)
    p.add_argument("--brand", type=Path, default=Path(__file__).resolve().parents[1] / "brand.json")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--notes", default="")
    p.add_argument("--url", help="download URL of the installer (default: derived from brand.json updateManifest)")
    args = p.parse_args()

    if not args.installer.is_file():
        sys.exit(f"No existe el instalador {args.installer}")
    brand = json.loads(args.brand.read_text(encoding="utf-8"))
    url = args.url or default_url(brand.get("updateManifest") or "", args.version, args.installer.name)
    manifest = {
        "version": args.version,
        "url": url,
        "sha256": sha256_file(args.installer),
        "size": args.installer.stat().st_size,
        "notes": args.notes,
        "published_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "signature": "",
    }
    args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Manifiesto (sin firmar) -> {args.out}")
    if not url:
        print("  Aviso: brand.json no tiene updateManifest; completá 'url' antes de firmar.")


if __name__ == "__main__":
    main()
